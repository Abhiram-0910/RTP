import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, String, Integer, DateTime, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from cachetools import TTLCache

from .database import engine, get_db, Base, init_db, close_db
from .models import Media
from .schemas import SearchRequest, SearchResponse, MediaResponse, RecommendationItem
from .recommendation_engine import HybridRecommendationEngine
from .ai_explainer import generate_explanations

logger = logging.getLogger(__name__)

# Inline Interaction model for future use
class Interaction(Base):
    __tablename__ = "interactions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

class InteractionRequest(BaseModel):
    tmdb_id: int
    action: str

# In-memory caches for fast retrieval
search_cache = TTLCache(maxsize=500, ttl=300)
trending_cache = TTLCache(maxsize=1, ttl=600)  # 10 minute cache for trending

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Movies and TV shows Recommendation Engine API lifespan...")
    try:
        await init_db()
        from .recommendation_engine import populate_faiss_fallback
        from .database import AsyncSessionFactory
        
        # Populate the required FAISS indices natively
        async with AsyncSessionFactory() as session:
            await populate_faiss_fallback(session)
            
    except Exception as e:
        logger.error("Failed to initialize database gracefully: %s", e)
    yield
    logger.info("Shutting down Movies and TV shows Recommendation Engine API...")
    await close_db()


app = FastAPI(
    title="Movies and TV shows Recommendation Engine API",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "healthy", "version": "2.0.0"}


@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest, db: AsyncSession = Depends(get_db)):
    query = request.query.strip() if request.query else ""
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Query cannot be empty"
        )
        
    # Standardize cache key components carefully to handle absent filters
    p_filter = str(request.platform_filter).lower().strip() if request.platform_filter else "none"
    g_filter = str(request.genre_filter).lower().strip() if request.genre_filter else "none"
    cache_key = f"{query.lower()}:{p_filter}:{g_filter}"
    
    if cache_key in search_cache:
        logger.info("Serving query '%s' from search cache.", query)
        return search_cache[cache_key]
        
    try:
        # Spin up Engine precisely as orchestrated within DB dependency context
        engine_instance = HybridRecommendationEngine(db)
        
        candidates, detected_lang = await engine_instance.recommend(
            query=query, 
            platform_filter=request.platform_filter, 
            genre_filter=request.genre_filter
        )
        
        # We need to extract the raw Media objects for Gemini Explanations limit to top 5
        top_5_media = [media for media, _score in candidates[:5]]
        explanations = await generate_explanations(query, top_5_media, detected_lang)
        
        # Stitch it together seamlessly
        results = []
        for media, score in candidates:
            media_resp = MediaResponse(
                id=media.id,
                tmdb_id=media.tmdb_id,
                title=media.title,
                media_type=media.media_type,
                overview=media.overview,
                genres=media.genres or [],
                cast_names=media.cast_names or [],
                release_date=media.release_date,
                vote_average=media.vote_average,
                popularity=media.popularity,
                poster_path=media.poster_path,
                platforms=media.platforms,
                created_at=media.created_at
            )
            # Fetch the dynamic explanation using TMDB ID natively, default gracefully if not top 5
            expl = explanations.get(media.tmdb_id, "Recommended based on thematic similarity to your query.")
            
            results.append(
                RecommendationItem(
                    media=media_resp, 
                    score=round(score, 4), 
                    explanation=expl
                )
            )
            
        final_response = SearchResponse(
            results=results, 
            query_language=detected_lang, 
            total=len(results)
        )
        
        # Store securely within Cachetools schema
        search_cache[cache_key] = final_response
        return final_response
        
    except Exception as e:
        logger.exception("A severe fault occurred handling the Search query '%s'", query)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/trending", response_model=List[MediaResponse])
async def trending(db: AsyncSession = Depends(get_db)):
    if "trending" in trending_cache:
        return trending_cache["trending"]
        
    try:
        # Execute direct SQL projection natively requesting top popular instances
        stmt = select(Media).order_by(Media.popularity.desc().nulls_last()).limit(20)
        result = await db.execute(stmt)
        items = result.scalars().all()
        
        responses = []
        for media in items:
            responses.append(MediaResponse(
                id=media.id,
                tmdb_id=media.tmdb_id,
                title=media.title,
                media_type=media.media_type,
                overview=media.overview,
                genres=media.genres or [],
                cast_names=media.cast_names or [],
                release_date=media.release_date,
                vote_average=media.vote_average,
                popularity=media.popularity,
                poster_path=media.poster_path,
                platforms=media.platforms,
                created_at=media.created_at
            ))
            
        trending_cache["trending"] = responses
        return responses
        
    except Exception as e:
        logger.exception("An error occurred fetching standard trending list.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/api/interact")
async def process_interaction(req: InteractionRequest, db: AsyncSession = Depends(get_db)):
    try:
        # Log the deterministic user behavior payload internally to DB logic
        new_interact = Interaction(tmdb_id=req.tmdb_id, action=req.action)
        db.add(new_interact)
        await db.commit()
        
        logger.info("Successfully recorded '%s' interaction against TMDB ID %d", req.action, req.tmdb_id)
        return {"status": "recorded"}
        
    except Exception as e:
        await db.rollback()
        logger.exception("Failed storing the interaction payload securely.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
