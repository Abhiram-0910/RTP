"""
main.py — FastAPI entry-point for Movie & TV Recommendation Engine.

Security
--------
- /token           : OAuth2 password flow (issues access + refresh JWT pair)
- /api/register    : create a new user account
- /api/refresh     : exchange refresh token for a new token pair
- /api/rate        : requires valid JWT bearer token; user_id from token
- /api/recommend   : open (public query), cached in Redis when available
- /api/ingest      : admin-only, enqueues data-ingestion Celery task

Caching
-------
Redis is used when REDIS_URL is set (or Redis is reachable at localhost:6379).
Falls back silently to no-cache if Redis is unavailable.
"""

import hashlib
import json
import os
from contextlib import asynccontextmanager
from typing import Optional

import redis
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from auth import (
    Token,
    get_current_user,
    require_admin,
    router as auth_router,
)
from datetime import timedelta
from database import get_db, Interaction, Media, init_db
from rag_engine import RecommendationEngine
from schemas import UserQuery, InteractionRequest, WatchlistAction

load_dotenv()

# ── Startup / shutdown lifespan ───────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables and seed admin user before accepting requests."""
    init_db()
    yield

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Movie & TV Recommendation Engine API",
    description="Hybrid FAISS + collaborative-filtering recommendation API with JWT auth and Redis caching.",
    version="2.0.0",
    lifespan=lifespan,
)

_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8501,http://127.0.0.1:8501,http://localhost:5173,http://127.0.0.1:5173",
)
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── CORS-safe exception handler ───────────────────────────────────────────────
# FastAPI's CORSMiddleware does NOT add CORS headers to error responses (4xx/5xx).
# Without this handler, a 401 from the backend shows up in the browser as a
# phantom "CORS policy" error, hiding the real problem.
@app.exception_handler(Exception)
async def _cors_safe_exception_handler(request: Request, exc: Exception):
    origin = request.headers.get("origin", "")
    status_code = exc.status_code if isinstance(exc, HTTPException) else 500
    detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
    headers = {}
    if origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
        headers=headers,
    )

# Register auth router (exposes /token)
app.include_router(auth_router)

# ── Recommendation Engine ─────────────────────────────────────────────────────

rec_engine = RecommendationEngine()

# ── Redis Cache ───────────────────────────────────────────────────────────────

CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))  # 5 min default
_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> Optional[redis.Redis]:
    """Return a Redis client, or None if unavailable (graceful degradation)."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        client = redis.from_url(_REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        client.ping()  # validate connectivity at startup
        _redis_client = client
        print(f"[cache] Redis connected at {_REDIS_URL}")
    except Exception as e:
        print(f"[cache] Redis unavailable — caching disabled ({e})")
        _redis_client = None
    return _redis_client


def _cache_key(request: UserQuery) -> str:
    """Deterministic cache key derived from all query fields."""
    raw = json.dumps(
        {
            "q": request.query.strip().lower(),
            "uid": request.user_id,
            "genre": request.genre,
            "min_rating": request.min_rating,
            "media_type": request.media_type,
        },
        sort_keys=True,
    )
    return "rec:" + hashlib.sha256(raw.encode()).hexdigest()


# ── Auth Endpoints ─────────────────────────────────────────────────────────────
# /token, /api/register, and /api/refresh are all provided by auth_router.
# No shadow routes needed here — auth_router is already included above.


# ── Health Check Endpoint ─────────────────────────────────────────────────────

@app.get("/api/health", tags=["system"])
async def health_check():
    """Returns service health status and backend component availability."""
    r = _get_redis()
    return {
        "status": "ok",
        "version": "2.0.0",
        "vector_backend": "faiss" if not os.getenv("USE_PGVECTOR") else "pgvector",
        "redis": "connected" if r else "unavailable",
        "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
    }


# ── Recommendation Endpoint (cached, public) ──────────────────────────────────

@app.post("/api/recommend", tags=["recommendations"])
async def get_recommendations(request: UserQuery, db: Session = Depends(get_db)):
    """
    Returns personalised movie & TV recommendations.

    Responses are cached in Redis for CACHE_TTL_SECONDS (default 5 min).
    The cache key incorporates all query parameters so different filter
    combinations are cached independently.
    """
    cache_key = _cache_key(request)
    r = _get_redis()

    # Cache read
    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                result = json.loads(cached)
                result["cached"] = True
                return result
        except Exception as e:
            print(f"[cache] Read error — bypassing cache: {e}")

    # Cache miss — run the engine
    result = rec_engine.get_recommendations(
        query=request.query,
        user_id=request.user_id,
        genre=request.genre,
        min_rating=request.min_rating,
        media_type=request.media_type,
    )
    result["cached"] = False

    # Cache write (best-effort)
    if r:
        try:
            r.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(result))
        except Exception as e:
            print(f"[cache] Write error — result not cached: {e}")

    return result


# ── Rate Endpoint (JWT-protected) ─────────────────────────────────────────────

@app.post("/api/rate", tags=["interactions"])
async def rate_recommendation(
    request: InteractionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Record a like/dislike interaction.

    The authenticated user's identity is sourced from the JWT token (sub claim).
    The request body no longer accepts a plaintext user_id — this prevents
    clients from spoofing interactions for other users.
    """
    user_id = current_user["username"]  # authoritative identity from token

    # Handle 'remove' — delete any existing interaction for this title
    if request.interaction_type == "remove":
        db.query(Interaction).filter(
            Interaction.user_id == user_id,
            Interaction.tmdb_id == request.tmdb_id,
        ).delete()
        db.commit()
        return {"status": "success", "message": f"Removed interaction for {request.tmdb_id}"}

    existing = db.query(Interaction).filter(
        Interaction.user_id == user_id,
        Interaction.tmdb_id == request.tmdb_id,
    ).first()

    if existing:
        existing.interaction_type = request.interaction_type
    else:
        db.add(Interaction(
            user_id=user_id,
            tmdb_id=request.tmdb_id,
            interaction_type=request.interaction_type,
        ))

    db.commit()
    return {
        "status": "success",
        "message": f"Recorded '{request.interaction_type}' for title {request.tmdb_id}",
        "user_id": user_id,
    }


# ── Watchlist Endpoints ────────────────────────────────────────────────────────

@app.get("/api/watchlist", tags=["watchlist"])
async def get_watchlist(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return the authenticated user's watchlist (all 'watchlist' interactions)."""
    user_id = current_user["username"]
    interactions = (
        db.query(Interaction)
        .filter(Interaction.user_id == user_id, Interaction.interaction_type == "watchlist")
        .all()
    )
    items = []
    for i in interactions:
        media = db.query(Media).filter(Media.tmdb_id == i.tmdb_id).first()
        if media:
            items.append({
                "id": media.tmdb_id,
                "title": media.title,
                "poster_path": media.poster_path,
                "rating": media.rating,
                "media_type": media.media_type,
                "release_date": media.release_date,
            })
    return {"watchlist": items, "count": len(items)}


@app.post("/api/watchlist", tags=["watchlist"])
async def modify_watchlist(
    request: WatchlistAction,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add or remove a title from the authenticated user's watchlist."""
    user_id = current_user["username"]
    existing = db.query(Interaction).filter(
        Interaction.user_id == user_id,
        Interaction.tmdb_id == request.tmdb_id,
        Interaction.interaction_type == "watchlist",
    ).first()

    if request.action == "remove":
        if existing:
            db.delete(existing)
            db.commit()
        return {"status": "removed", "tmdb_id": request.tmdb_id}
    else:  # add
        if not existing:
            db.add(Interaction(user_id=user_id, tmdb_id=request.tmdb_id, interaction_type="watchlist"))
            db.commit()
        return {"status": "added", "tmdb_id": request.tmdb_id}


@app.get("/api/user_stats", tags=["watchlist"])
async def get_user_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return interaction counts for the authenticated user."""
    user_id = current_user["username"]
    interactions = db.query(Interaction).filter(Interaction.user_id == user_id).all()
    liked    = [i for i in interactions if i.interaction_type == "like"]
    disliked = [i for i in interactions if i.interaction_type == "dislike"]
    watchlist = [i for i in interactions if i.interaction_type == "watchlist"]
    return {
        "user_id": user_id,
        "movies_liked": len(liked),
        "movies_disliked": len(disliked),
        "watchlist_size": len(watchlist),
        "total_interactions": len(interactions),
    }


# ── Admin: Trigger Data Ingestion (Celery task) ───────────────────────────────

@app.post("/api/ingest", tags=["admin"])
async def trigger_ingestion(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_admin),
):
    """
    Admin-only: enqueue a full data-ingestion run as a background task.

    Uses Celery if the broker is reachable, otherwise runs via FastAPI
    BackgroundTasks so it never blocks the request thread either way.
    """
    try:
        from tasks import dispatch_ingest_data
        background_tasks.add_task(dispatch_ingest_data)
        return {
            "status": "queued",
            "message": "Data ingestion task dispatched.",
            "triggered_by": current_user["username"],
        }
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tasks module not available.",
        )


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health():
    r = _get_redis()
    redis_ok = False
    if r:
        try:
            r.ping()
            redis_ok = True
        except Exception:
            pass
    return {"status": "ok", "redis": redis_ok}