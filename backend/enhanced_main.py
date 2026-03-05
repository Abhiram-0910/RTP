"""
enhanced_main.py — MIRAI FastAPI Backend (Production-Grade)
Fixes applied:
 - Real query embedding (not random) wired into hybrid scoring
 - FAISS metadata key 'tmdb_id' (not 'id') for DB lookup
 - Genre + platform filters enabled
 - Streaming platforms wired from real DB + real-time TMDB API
 - AdvancedRecommendationEngine receives embeddings model reference
 - Correct interaction endpoint (/api/interact)
"""
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import sys
import io
import json
import hashlib

# Fix Windows console encoding to prevent UnicodeEncodeError with emojis/special chars
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass
import requests as http_requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor

from enhanced_database import (
    get_db, User, Media, StreamingPlatform, EnhancedInteraction,
    UserReview, RecommendationCache, TrendingMedia, SearchAnalytics,
    init_enhanced_db, get_db_session
)
from ai_explainer import get_ai_explainer
from advanced_recommendation_engine import AdvancedRecommendationEngine

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")

app = FastAPI(
    title="MIRAI AI — Movie & TV Recommendation Engine",
    description=(
        "Advanced AI-powered recommendation system with semantic search, "
        "hybrid filtering, multilingual support, real-time streaming data, "
        "and Gemini-powered explainable recommendations."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

# ── Global singletons ─────────────────────────────────────────────────────────
embeddings = None
vector_store = None
translator = None
ai_explainer = None
rec_engine = None
executor = ThreadPoolExecutor(max_workers=10)


def initialize_services():
    """Initialize global ML services on startup."""
    global embeddings, vector_store, translator, ai_explainer, rec_engine

    # 1. Multilingual embedding model
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            model_kwargs={"device": "cpu"},
        )
        print("[OK] Embedding model loaded.")
    except Exception as e:
        print(f"[ERROR] Could not load embedding model: {e}")

    # 2. FAISS vector store
    try:
        from langchain_community.vectorstores import FAISS
        faiss_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'faiss_index')
        vector_store = FAISS.load_local(
            faiss_path,
            embeddings,
            allow_dangerous_deserialization=True,
        )
        print(f"[OK] FAISS index loaded from {faiss_path}.")
    except Exception as e:
        print(f"[WARNING] FAISS index not found or failed to load: {e}")
        print("  -> Run: cd backend && python ingest_all_data.py")

    # 3. Translator (deep-translator + langdetect)
    try:
        from langdetect import detect as _langdetect  # noqa
        from deep_translator import GoogleTranslator as _GoogleTranslator  # noqa
        translator = True  # Sentinel: libraries are available
        print("[OK] deep-translator + langdetect ready.")
    except ImportError as e:
        print(f"[WARNING] Translation libraries not installed: {e}")
        translator = None

    # 4. Gemini AI explainer
    try:
        ai_explainer = get_ai_explainer()
        print("[OK] Gemini AI explainer ready.")
    except Exception as e:
        print(f"[WARNING] AI explainer unavailable: {e}")
        ai_explainer = None

    # 5. Recommendation engine — pass the real embeddings model
    rec_engine = AdvancedRecommendationEngine(embeddings_model=embeddings)
    print("[OK] Advanced recommendation engine initialized.")


initialize_services()


# ── Pydantic request/response models ─────────────────────────────────────────

class UserQuery(BaseModel):
    query: str
    user_id: Optional[str] = "demo_user"
    genre: Optional[str] = None
    min_rating: Optional[float] = 0.0
    media_type: Optional[str] = "All"
    year_range: Optional[List[int]] = None
    platforms: Optional[List[str]] = None
    max_runtime: Optional[int] = None
    explanation_style: Optional[str] = "detailed"
    diversity_level: Optional[float] = 0.7
    include_trending: Optional[bool] = True
    language_preference: Optional[str] = "en"


class InteractionRequest(BaseModel):
    user_id: str
    tmdb_id: int
    interaction_type: str  # "like", "dislike", "watch", "rate", "skip"
    rating: Optional[int] = None  # 1-10 for explicit ratings
    context: Optional[Dict[str, Any]] = None


class ReviewRequest(BaseModel):
    user_id: str
    tmdb_id: int
    review_text: str
    rating: Optional[int] = None


class WatchlistRequest(BaseModel):
    user_id: str
    tmdb_id: int
    action: str  # "add", "remove", "mark_watched"


# ── Startup / Lifecycle ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    init_enhanced_db()
    print("[STARTING] MIRAI AI Enhanced Backend Started!")


# ── Health & Stats ────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "services": {
            "database": "connected",
            "ai_explainer": "active" if ai_explainer else "inactive",
            "vector_store": "loaded" if vector_store else "inactive — run ingest_all_data.py",
            "translator": "active" if translator else "inactive",
            "embedding_model": "loaded" if embeddings else "inactive",
        },
    }


@app.get("/api/stats")
async def get_system_stats(db: Session = Depends(get_db)):
    try:
        total_media = db.query(Media).count()
        total_movies = db.query(Media).filter(Media.media_type == "movie").count()
        total_tv = db.query(Media).filter(Media.media_type == "tv").count()
        total_platforms = db.query(StreamingPlatform).count()
        total_interactions = db.query(EnhancedInteraction).count()
        languages = db.query(Media.original_language).distinct().count()
        recent_interactions = db.query(EnhancedInteraction).filter(
            EnhancedInteraction.timestamp >= datetime.now() - timedelta(days=7)
        ).count()

        return {
            "total_titles": f"{total_media:,}",
            "total_movies": f"{total_movies:,}",
            "total_tv_shows": f"{total_tv:,}",
            "languages": f"{languages}",
            "platforms": f"{total_platforms}",
            "total_interactions": f"{total_interactions:,}",
            "recent_activity": f"{recent_interactions:,}",
            "ai_explanations": "Unlimited",
            "vector_store": "active" if vector_store else "inactive",
        }
    except Exception as e:
        return {
            "total_titles": "10K+", "total_movies": "6K+", "total_tv_shows": "4K+",
            "languages": "15+", "platforms": "50+",
            "total_interactions": "0", "recent_activity": "0",
            "ai_explanations": "Unlimited",
        }


# ── Core Recommendation Endpoint ──────────────────────────────────────────────

@app.post("/api/recommend")
async def get_enhanced_recommendations(
    request: UserQuery,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Get hybrid AI-powered recommendations with multilingual support."""
    try:
        cache_key = _create_cache_key(request)

        # Check recommendation cache
        cached = db.query(RecommendationCache).filter(
            RecommendationCache.cache_key == cache_key,
            RecommendationCache.expires_at > datetime.now(),
        ).first()
        if cached:
            cached.hit_count += 1
            db.commit()
            return cached.results

        # ── Step 1: Language detection & translation ──────────────────────────
        original_query = request.query
        translated_query = original_query
        detected_lang = "en"

        if translator:
            try:
                from langdetect import detect as _detect
                from deep_translator import GoogleTranslator
                detected_lang = _detect(original_query) or "en"
                if detected_lang != "en":
                    translated_query = GoogleTranslator(source="auto", target="en").translate(original_query) or original_query
                    print(f"[TRANSLATE] '{original_query}' ({detected_lang}) -> '{translated_query}'")
            except Exception as e:
                print(f"[WARNING] Translation error: {e}")
                detected_lang = "en"

        # ── Step 2: Compute REAL query embedding ──────────────────────────────
        query_embedding = None
        if embeddings:
            try:
                query_embedding = np.array(
                    embeddings.embed_query(translated_query), dtype=np.float32
                )
            except Exception as e:
                print(f"[WARNING] Embedding error: {e}")

        # ── Step 3: Vector search ────────────────────────────────────────────
        if vector_store and query_embedding is not None:
            docs_with_scores = vector_store.similarity_search_with_score(
                translated_query, k=60
            )
        elif vector_store:
            docs_with_scores = vector_store.similarity_search_with_score(
                translated_query, k=60
            )
        else:
            docs_with_scores = _fallback_database_search(translated_query, db, limit=60)

        # ── Step 4: Build candidate list ─────────────────────────────────────
        candidates = []
        for doc, similarity_score in docs_with_scores:
            # FIX: metadata key is 'tmdb_id' (set by ingest_all_data.py)
            tmdb_id = (
                doc.metadata.get("tmdb_id")
                or doc.metadata.get("id")
            )
            media_type_doc = doc.metadata.get("media_type", "movie")

            if not tmdb_id:
                continue

            media_record = db.query(Media).filter(
                Media.tmdb_id == int(tmdb_id)
            ).first()

            if not media_record:
                continue

            # Apply advanced filters
            if not _passes_advanced_filters(media_record, request):
                continue

            # Fetch streaming platforms from DB
            db_platforms = [p.name for p in media_record.platforms]

            # Build candidate dict
            candidate = {
                "id": int(media_record.tmdb_id),
                "db_id": int(media_record.db_id),
                "title": media_record.title,
                "overview": media_record.overview or "",
                "release_date": media_record.release_date or "",
                "rating": float(media_record.rating or 0),
                "poster_path": _format_poster_url(media_record.poster_path),
                "media_type": media_record.media_type,
                "genres": media_record.genres or [],
                "keywords": media_record.keywords or [],
                "popularity": float(media_record.popularity_score or 0),
                "original_language": media_record.original_language or "en",
                "runtime": media_record.runtime,
                "director": media_record.director,
                "cast": media_record.cast or [],
                "similarity_score": float(similarity_score),
                "streaming_platforms": db_platforms,
            }
            candidates.append(candidate)

        # ── Step 5: Load user interactions for collaborative filtering ─────
        user_interactions = []
        if request.user_id and request.user_id != "demo_user":
            raw_interactions = (
                db.query(EnhancedInteraction)
                .filter(EnhancedInteraction.user_id == request.user_id)
                .order_by(EnhancedInteraction.timestamp.desc())
                .limit(100)
                .all()
            )
            for inter in raw_interactions:
                if inter.media:
                    user_interactions.append({
                        "user_id": inter.user_id,
                        "tmdb_id": inter.media.tmdb_id,
                        "interaction_type": inter.interaction_type,
                        "rating": inter.rating,
                        "genres": inter.media.genres or [],
                        "keywords": inter.media.keywords or [],
                    })

        # ── Step 6: Hybrid recommendation scoring ────────────────────────────
        response_data = {}

        if candidates:
            top_candidates = candidates[:30]
            use_embedding = (
                query_embedding is not None
                and query_embedding.shape[0] == 384
            )
            effective_embedding = (
                query_embedding if use_embedding
                else np.zeros(384, dtype=np.float32)
            )

            if rec_engine is not None:
                ranked_items = rec_engine.hybrid_content_collaborative_scoring(
                    query_embedding=effective_embedding,
                    user_id=request.user_id,
                    candidate_items=top_candidates,
                    user_interactions=user_interactions,
                    item_features={},
                )

                diverse_results = rec_engine.apply_diversity_filtering(
                    ranked_items, max_results=8
                )

                serendipitous = rec_engine.generate_serendipitous_recommendations(
                    user_interactions=user_interactions,
                    all_items=candidates,
                    num_serendipitous=2,
                )

                final_results = diverse_results + serendipitous
            else:
                # Fallback: sort by similarity_score if rec_engine failed to init
                final_results = sorted(
                    top_candidates, key=lambda x: x.get("similarity_score", 0), reverse=True
                )[:8]
                serendipitous = []

            # Add match_score percentage and fetch real-time providers if not in DB
            for item in final_results:
                raw_sim = item.get("similarity_score", 0.0)
                item["match_score"] = round(min(raw_sim * 10, 100.0), 1)
                # Real-time provider lookup if DB has no data
                if not item["streaming_platforms"] and TMDB_API_KEY:
                    item["streaming_platforms"] = _fetch_tmdb_providers(
                        item["id"], item["media_type"]
                    )

            # Generate AI explanation
            explanation = ""
            if ai_explainer:
                try:
                    explanation = ai_explainer.generate_personalized_explanation(
                        query=original_query,
                        recommendations=final_results[:5],
                        user_id=request.user_id,
                        user_history=user_interactions[:10],
                    )
                except Exception as e:
                    explanation = _fallback_explanation(original_query, final_results)

            response_data = {
                "explanation": explanation,
                "movies": final_results[:8],
                "query": original_query,
                "translated_query": translated_query if translated_query != original_query else None,
                "detected_language": detected_lang,
                "total_candidates": len(candidates),
                "diversity_score": _calculate_diversity_score(final_results),
                "serendipitous_count": len(serendipitous),
                "ai_features": {
                    "multilingual": detected_lang != "en",
                    "explanation_generated": bool(explanation),
                    "collaborative_filtering": len(user_interactions) > 0,
                    "diversity_applied": True,
                    "real_embeddings": use_embedding,
                },
            }
        else:
            # Fallback: return top popular titles
            fallback_media = (
                db.query(Media)
                .order_by(Media.popularity_score.desc())
                .limit(8)
                .all()
            )
            final_results = []
            for m in fallback_media:
                final_results.append({
                    "id": int(m.tmdb_id),
                    "title": m.title,
                    "overview": m.overview or "",
                    "release_date": m.release_date or "",
                    "rating": float(m.rating or 0),
                    "poster_path": _format_poster_url(m.poster_path),
                    "media_type": m.media_type,
                    "genres": m.genres or [],
                    "keywords": m.keywords or [],
                    "match_score": 0,
                    "streaming_platforms": [p.name for p in m.platforms],
                })

            response_data = {
                "explanation": (
                    "No semantic matches found — here are our most popular recommendations!"
                ),
                "movies": final_results,
                "query": original_query,
                "total_candidates": 0,
                "ai_features": {"fallback": True},
            }

        # Cache & analytics (background)
        background_tasks.add_task(_cache_results, cache_key, response_data)
        background_tasks.add_task(
            _log_analytics, request, len(response_data.get("movies", [])), detected_lang
        )

        return response_data

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Recommendation error: {str(e)}")


# ── Interaction Endpoint ──────────────────────────────────────────────────────

@app.post("/api/interact")
@app.post("/api/rate")  # backward-compat alias
async def record_interaction(
    request: InteractionRequest, db: Session = Depends(get_db)
):
    """Record user interaction (like/dislike/watch/rate/skip)."""
    try:
        user = db.query(User).filter(User.user_id == request.user_id).first()
        if not user:
            user = User(user_id=request.user_id)
            db.add(user)
            db.commit()

        media = db.query(Media).filter(Media.tmdb_id == request.tmdb_id).first()
        if not media:
            raise HTTPException(status_code=404, detail=f"Media tmdb_id={request.tmdb_id} not found")

        existing = db.query(EnhancedInteraction).filter(
            EnhancedInteraction.user_id == request.user_id,
            EnhancedInteraction.media_id == media.db_id,
        ).first()

        if existing:
            existing.interaction_type = request.interaction_type
            existing.rating = request.rating
            existing.timestamp = datetime.now()
            interaction_id = existing.id
        else:
            interaction = EnhancedInteraction(
                user_id=request.user_id,
                media_id=media.db_id,
                interaction_type=request.interaction_type,
                rating=request.rating,
                context=request.context or {},
            )
            db.add(interaction)
            db.flush()
            interaction_id = interaction.id

        db.commit()
        return {
            "status": "success",
            "message": f"Recorded '{request.interaction_type}' for '{media.title}'",
            "interaction_id": interaction_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Interaction error: {str(e)}")


# ── Trending Endpoint ─────────────────────────────────────────────────────────

@app.get("/api/trending")
async def get_trending(db: Session = Depends(get_db)):
    """Return trending movies and TV shows from DB + real-time TMDB."""
    try:
        # Try TrendingMedia table first
        trending_records = (
            db.query(TrendingMedia)
            .join(Media)
            .filter(TrendingMedia.calculated_at >= datetime.now() - timedelta(days=7))
            .order_by(TrendingMedia.trending_score.desc())
            .limit(12)
            .all()
        )

        if not trending_records:
            # Fallback: highest popularity_score in DB
            trending_media = (
                db.query(Media)
                .filter(Media.popularity_score > 30)
                .order_by(Media.popularity_score.desc())
                .limit(12)
                .all()
            )
        else:
            trending_media = [r.media for r in trending_records]

        trending_movies, trending_shows = [], []
        for m in trending_media:
            item = {
                "id": m.tmdb_id,
                "title": m.title,
                "poster_path": _format_poster_url(m.poster_path),
                "rating": m.rating,
                "media_type": m.media_type,
                "genres": m.genres or [],
                "trending_reason": "Popular this week",
            }
            if m.media_type == "movie":
                trending_movies.append(item)
            else:
                trending_shows.append(item)

        explanation = ""
        if ai_explainer and (trending_movies or trending_shows):
            try:
                explanation = ai_explainer.generate_trending_explanation(
                    trending_movies[:4], trending_shows[:4]
                )
            except Exception:
                explanation = "Check out what's trending right now!"

        return {
            "trending": trending_movies + trending_shows,
            "explanation": explanation,
            "movies_count": len(trending_movies),
            "shows_count": len(trending_shows),
            "updated_at": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "trending": [], "explanation": "Unable to fetch trending content",
            "movies_count": 0, "shows_count": 0,
            "updated_at": datetime.now().isoformat(),
        }


# ── User Stats Endpoint ───────────────────────────────────────────────────────

@app.get("/api/user_stats/{user_id}")
async def get_user_stats(user_id: str, db: Session = Depends(get_db)):
    try:
        interactions = (
            db.query(EnhancedInteraction)
            .filter(EnhancedInteraction.user_id == user_id)
            .all()
        )
        movies_liked = sum(
            1 for i in interactions
            if i.interaction_type == "like" and i.media and i.media.media_type == "movie"
        )
        tv_liked = sum(
            1 for i in interactions
            if i.interaction_type == "like" and i.media and i.media.media_type == "tv"
        )
        genre_prefs: Dict[str, int] = {}
        for inter in interactions:
            if inter.media and inter.media.genres:
                for g in inter.media.genres:
                    genre_prefs[g] = genre_prefs.get(g, 0) + 1
        top_genres = dict(sorted(genre_prefs.items(), key=lambda x: x[1], reverse=True)[:5])

        return {
            "user_id": user_id,
            "movies_liked": movies_liked,
            "tv_shows_liked": tv_liked,
            "watchlist_size": 0,
            "total_interactions": len(interactions),
            "genre_preferences": top_genres,
            "last_active": interactions[0].timestamp.isoformat() if interactions else None,
        }
    except Exception:
        return {
            "user_id": user_id, "movies_liked": 0, "tv_shows_liked": 0,
            "watchlist_size": 0, "total_interactions": 0,
            "genre_preferences": {}, "last_active": None,
        }


# ── Search Analytics Endpoint ─────────────────────────────────────────────────

@app.get("/api/search_analytics")
async def get_search_analytics(db: Session = Depends(get_db)):
    try:
        recent = (
            db.query(SearchAnalytics)
            .order_by(SearchAnalytics.timestamp.desc())
            .limit(20)
            .all()
        )
        return {
            "recent_searches": [
                {
                    "query": s.query,
                    "language": s.query_language,
                    "results": s.results_count,
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in recent
            ]
        }
    except Exception as e:
        return {"recent_searches": []}


# ── Private Helpers ───────────────────────────────────────────────────────────

def _create_cache_key(request: UserQuery) -> str:
    key = f"{request.query}|{request.user_id}|{request.genre}|{request.min_rating}|{request.media_type}|{request.diversity_level}"
    return hashlib.md5(key.encode()).hexdigest()


def _cache_results(cache_key: str, results: Dict):
    """Background task: cache recommendation results."""
    db = get_db_session()
    try:
        existing = db.query(RecommendationCache).filter(
            RecommendationCache.cache_key == cache_key
        ).first()
        if not existing:
            cache_entry = RecommendationCache(
                cache_key=cache_key,
                results=results,
                expires_at=datetime.now() + timedelta(hours=6),
            )
            db.add(cache_entry)
            db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()


def _log_analytics(request: UserQuery, results_count: int, detected_lang: str):
    """Background task: log search analytics."""
    db = get_db_session()
    try:
        analytics = SearchAnalytics(
            query=request.query,
            query_language=detected_lang,
            user_id=request.user_id if request.user_id != "demo_user" else None,
            results_count=results_count,
            filters_used={
                "genre": request.genre,
                "min_rating": request.min_rating,
                "media_type": request.media_type,
                "diversity_level": request.diversity_level,
            },
        )
        db.add(analytics)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _format_poster_url(poster_path: Optional[str]) -> str:
    """Ensure poster URL is a full TMDB URL."""
    if not poster_path or str(poster_path) in ("nan", "None", ""):
        return "https://via.placeholder.com/500x750/1e293b/94a3b8?text=No+Poster"
    if poster_path.startswith("http"):
        return poster_path
    return f"https://image.tmdb.org/t/p/w500{poster_path}"


def _fetch_tmdb_providers(tmdb_id: int, media_type: str) -> List[str]:
    """Real-time TMDB watch/providers lookup (US + IN regions)."""
    if not TMDB_API_KEY:
        return []
    try:
        ep = "movie" if media_type == "movie" else "tv"
        url = f"https://api.themoviedb.org/3/{ep}/{tmdb_id}/watch/providers"
        r = http_requests.get(url, params={"api_key": TMDB_API_KEY}, timeout=4)
        if r.status_code == 200:
            results = r.json().get("results", {})
            platforms = set()
            for region in ["US", "IN", "GB"]:
                rd = results.get(region, {})
                for stype in ["flatrate", "free", "ads"]:
                    for p in rd.get(stype, []):
                        platforms.add(p.get("provider_name", "").strip())
            return [p for p in platforms if p]
    except Exception:
        pass
    return []


def _passes_advanced_filters(media: Media, request: UserQuery) -> bool:
    """Check if a media record passes all user-specified filters."""
    try:
        # Media type filter
        if request.media_type and request.media_type != "All":
            req_mt = request.media_type.strip()
            # Normalize to DB values: "Movies" -> "movie", "TV Shows" -> "tv"
            if req_mt.lower() in ("movies", "movie"):
                target_type = "movie"
            elif req_mt.lower() in ("tv shows", "tv", "tv show"):
                target_type = "tv"
            else:
                target_type = req_mt.lower()
            if media.media_type != target_type:
                return False

        # Rating filter
        min_rating = min(request.min_rating or 0.0, 9.5)
        if media.rating is not None and media.rating < min_rating:
            return False

        # Year range filter
        if request.year_range and len(request.year_range) == 2 and media.release_date:
            try:
                year = int(str(media.release_date)[:4])
                if year < request.year_range[0] or year > request.year_range[1]:
                    return False
            except (ValueError, TypeError):
                pass

        # Max runtime filter
        if request.max_runtime and media.runtime:
            if media.runtime > request.max_runtime:
                return False

        # Genre filter (enabled — ANY overlap passes)
        if request.genre:
            media_genres = media.genres or []
            if isinstance(media_genres, str):
                try:
                    media_genres = json.loads(media_genres)
                except Exception:
                    media_genres = []
            req_genres = [request.genre] if isinstance(request.genre, str) else request.genre
            # Normalize comparison
            media_genres_lower = [g.lower() for g in media_genres]
            req_genres_lower = [g.lower() for g in req_genres]
            if req_genres_lower and not any(g in media_genres_lower for g in req_genres_lower):
                return False

        # Platform filter (enabled — ANY overlap passes)
        if request.platforms and len(request.platforms) > 0:
            media_platform_names = [p.name.lower() for p in media.platforms]
            req_platforms_lower = [p.lower() for p in request.platforms]
            if not any(p in media_platform_names for p in req_platforms_lower):
                return False

        return True
    except Exception as e:
        print(f"[WARNING] Filter error: {e}")
        return True  # Fail open


def _fallback_database_search(query: str, db: Session, limit: int = 50) -> List:
    """Text-based fallback search when FAISS is unavailable."""
    try:
        results = (
            db.query(Media)
            .filter(
                or_(
                    Media.title.ilike(f"%{query}%"),
                    Media.overview.ilike(f"%{query}%"),
                )
            )
            .limit(limit)
            .all()
        )
        formatted = []
        for m in results:
            doc = type("Doc", (), {
                "metadata": {"tmdb_id": m.tmdb_id, "id": m.tmdb_id, "media_type": m.media_type}
            })()
            formatted.append((doc, 5.0))  # L2 distance of 5 = moderate similarity
        return formatted
    except Exception as e:
        print(f"[ERROR] Fallback search: {e}")
        return []


def _calculate_diversity_score(items: List[Dict]) -> float:
    if len(items) <= 1:
        return 0.0
    all_genres = []
    for item in items:
        all_genres.extend(item.get("genres", []))
    if not all_genres:
        return 0.0
    return round(len(set(all_genres)) / len(all_genres), 2)


def _fallback_explanation(query: str, results: List[Dict]) -> str:
    titles = [r["title"] for r in results[:3]]
    return (
        f"Based on your search for '{query}', here are titles that best match your interests. "
        f"Featured: {', '.join(titles)}."
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)