from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from rag_engine import RecommendationEngine
from database import get_db, Interaction
from schemas import UserQuery, InteractionRequest

load_dotenv()

app = FastAPI(title="MIRAI Movie & TV Recommendation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rec_engine = RecommendationEngine()

@app.post("/api/recommend")
async def get_recommendations(request: UserQuery, db: Session = Depends(get_db)):
    # Pass user_id, genre, min_rating, and media_type down to the engine
    return rec_engine.get_recommendations(
        query=request.query, 
        user_id=request.user_id,
        genre=request.genre,
        min_rating=request.min_rating,
        media_type=request.media_type
    )

@app.post("/api/rate")
async def rate_recommendation(request: InteractionRequest, db: Session = Depends(get_db)):
    # Check if interaction already exists to update it, or create a new one
    existing_interaction = db.query(Interaction).filter(
        Interaction.user_id == request.user_id,
        Interaction.tmdb_id == request.tmdb_id
    ).first()
    
    if existing_interaction:
        existing_interaction.interaction_type = request.interaction_type
    else:
        new_interaction = Interaction(
            user_id=request.user_id,
            tmdb_id=request.tmdb_id,
            interaction_type=request.interaction_type
        )
        db.add(new_interaction)
        
    db.commit()
    return {"status": "success", "message": f"Recorded {request.interaction_type} for title {request.tmdb_id}"}