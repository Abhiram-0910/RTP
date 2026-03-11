from pydantic import BaseModel
from typing import Optional

class UserQuery(BaseModel):
    query: str
    user_id: Optional[str] = "demo_user"
    genre: Optional[str] = None
    min_rating: Optional[float] = 0.0
    media_type: Optional[str] = "All" # "All", "Movies", "TV Shows"

class InteractionRequest(BaseModel):
    tmdb_id: int
    interaction_type: str  # "like" or "dislike"
