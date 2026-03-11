"""
main.py — FastAPI entry-point for Movie & TV Recommendation Engine.

Security
--------
- /token           : OAuth2 password flow (issues JWT)
- /api/rate        : requires valid JWT bearer token; user_id sourced from token
- /api/recommend   : open (public query), cached in Redis when available
- /api/ingest      : admin-only, enqueues data-ingestion Celery task

Caching
-------
Redis is used when REDIS_URL is set (or Redis is reachable at localhost:6379).
Falls back silently to no-cache if Redis is unavailable — the API never errors
because of a missing cache layer.
"""

import hashlib
import json
import os
from typing import Optional

import redis
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from auth import (
    Token,
    authenticate_user,
    create_access_token,
    get_current_user,
    require_admin,
    router as auth_router,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from datetime import timedelta
from database import get_db, Interaction
from rag_engine import RecommendationEngine
from schemas import UserQuery, InteractionRequest

load_dotenv()

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Movie & TV Recommendation Engine API",
    description="Hybrid FAISS + collaborative-filtering recommendation API with JWT auth and Redis caching.",
    version="2.0.0",
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
# /token is provided by auth_router. Expose it at root level too for OpenAPI docs.

@app.post("/token", response_model=Token, tags=["auth"], include_in_schema=False)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Shadow route — the real implementation is on auth_router."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=token, token_type="bearer", expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60)


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