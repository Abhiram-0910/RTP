"""
celery_tasks.py — Celery Beat periodic task scheduler for the MIRAI engine.

This module is the single entry-point for all *scheduled* background work.
Ad-hoc / request-triggered tasks live in tasks.py; periodic / cron work lives
here so the Beat schedule is in one obvious place.

Architecture overview
---------------------
                 ┌──────────────┐
 Celery Beat ──► │ Redis broker │ ──► Worker(s) ──► DB / Redis cache
                 └──────────────┘

Beat is a *lightweight scheduler* — it doesn't do the work itself, it just
publishes a task message to the broker on schedule. One or more workers pick
it up and execute it. Beat and Worker can run in the same process (solo mode,
good for dev) or as separate processes (recommended for production).

Startup (development — runs Beat + Worker in one process)
----------------------------------------------------------
    # From the backend/ directory:
    celery -A celery_tasks worker --beat --loglevel=info --pool=solo

Startup (production — separate processes for resilience)
---------------------------------------------------------
    # Terminal 1 — worker(s):
    celery -A celery_tasks worker --loglevel=info --concurrency=4

    # Terminal 2 — beat scheduler:
    celery -A celery_tasks beat --loglevel=info --scheduler=celery.beat:PersistentScheduler

    # Optional — Flower monitoring UI:
    celery -A celery_tasks flower --port=5555

Environment variables
---------------------
    REDIS_URL            Redis broker + result backend  (default: redis://localhost:6379/0)
    CELERY_BROKER_URL    Override broker separately      (default: REDIS_URL)
    CELERY_RESULT_BACKEND Override result backend        (default: REDIS_URL)
    TMDB_API_KEY         Required for live TMDB calls

Windows note
------------
    The default "prefork" worker pool is not supported on Windows.
    Always pass --pool=solo (single-threaded) or --pool=eventlet
    (pip install eventlet) when running on Windows.
"""

from __future__ import annotations

import json
import logging
import os
import pickle
from datetime import datetime, timezone
from typing import Any

from celery import Celery
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from dotenv import load_dotenv

# ── Environment ───────────────────────────────────────────────────────────────

load_dotenv()

_REDIS_URL      = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_BROKER_URL     = os.getenv("CELERY_BROKER_URL",     _REDIS_URL)
_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", _REDIS_URL)
_TMDB_API_KEY   = os.getenv("TMDB_API_KEY", "")

_TOP_N_TITLES = int(os.getenv("TRENDING_CACHE_BUST_LIMIT", "200"))
"""How many top titles' watch-provider caches to refresh per daily run."""

logger = get_task_logger(__name__)

# ── Celery application ────────────────────────────────────────────────────────

celery_app = Celery(
    "mirai_celery_tasks",
    broker=_BROKER_URL,
    backend=_RESULT_BACKEND,
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Reliability
    task_acks_late=True,          # Re-queue on hard worker failure
    worker_prefetch_multiplier=1, # One task at a time per worker — prevents RAM spikes

    # Result tombstone TTL — prevents Redis from growing unboundedly
    result_expires=3600,          # 1 hour
    result_extended=True,         # Renew TTL on result retrieval

    # Beat schedule ────────────────────────────────────────────────────────────
    # •  update_trending_and_providers: daily at 03:00 UTC (best practice: off-peak)
    # •  weekly_full_ingest:            Sundays at 02:00 UTC (heavier — runs weekly)
    beat_schedule={
        "update-trending-and-providers-daily": {
            "task": "celery_tasks.update_trending_and_providers",
            "schedule": crontab(hour=3, minute=0),          # 03:00 UTC every day
            "options": {"expires": 3600},
        },
        "weekly-full-data-ingest": {
            "task": "celery_tasks.full_data_ingest",
            "schedule": crontab(hour=2, minute=0, day_of_week=0),  # Sundays 02:00 UTC
            "options": {"expires": 7200},
        },
        # ALS model retrained every 5 minutes so all Uvicorn workers share
        # a single up-to-date model via Redis rather than training inline.
        "train-als-model-every-5-minutes": {
            "task": "celery_tasks.train_als_model_task",
            "schedule": 300,          # every 300 seconds = 5 minutes
            "options": {"expires": 240},  # drop if not picked up within 4 min
        },
    },
)


# ── Helper: Redis client (reuses the singleton already in rag_engine if available) ──

def _get_redis():
    """Return a redis.Redis client or None if Redis is unavailable."""
    try:
        import redis
        client = redis.from_url(_REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis unavailable in celery_tasks: %s", exc)
        return None


# ── Helper: Database session ──────────────────────────────────────────────────

def _get_db():
    """Return a SQLAlchemy session from the project's database module."""
    # Import inside the function so the Celery module can be imported
    # without the full FastAPI application stack being initialised.
    from backend.database import SessionLocal
    return SessionLocal()


# ═══════════════════════════════════════════════════════════════════════════════
# Task 1 — Daily: update trending data + refresh watch-provider cache
# ═══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    name="celery_tasks.update_trending_and_providers",
    bind=True,
    max_retries=3,
    default_retry_delay=300,   # 5-minute back-off between retries
    time_limit=1800,           # Hard kill after 30 minutes
    soft_time_limit=1500,      # SIGTERM warning at 25 minutes
    acks_late=True,
)
def update_trending_and_providers(self) -> dict[str, Any]:
    """
    Daily periodic task (03:00 UTC):

    Phase 1 — Trending refresh
        • Calls TMDB /trending/movie/week and /trending/tv/week
        • Upserts popularity score and rank_position into the ``Media`` table
          for every title found in the top 20 results per type

    Phase 2 — Watch-provider cache bust (Redis)
        • Fetches the top *N* titles by popularity from the database
          (N = TRENDING_CACHE_BUST_LIMIT, default 200)
        • Deletes their ``providers:*`` Redis cache keys so the next user
          request gets fresh JustWatch data (via rag_engine.get_watch_providers)

    Phase 3 — Watch-provider pre-warm (Redis)
        • Immediately re-fetches providers for the same top-N titles
          so the cache is pre-populated before users hit the API
        • Uses the same key schema as rag_engine: ``providers:{type}:{id}:{regions}``

    Returns a summary dict logged to Celery's result backend.
    """
    import requests as http_requests
    from backend.database import Media  # local import — avoids FastAPI startup side-effects

    if not _TMDB_API_KEY:
        logger.error("[update_trending_and_providers] TMDB_API_KEY is not set — aborting.")
        return {"status": "error", "reason": "TMDB_API_KEY missing"}

    run_start = datetime.now(timezone.utc).isoformat()
    stats: dict[str, Any] = {
        "started_at": run_start,
        "trending_updated": 0,
        "cache_busted": 0,
        "cache_warmed": 0,
        "errors": [],
    }

    # ── Phase 1: Trending refresh ─────────────────────────────────────────────
    logger.info("[Phase 1] Refreshing trending scores from TMDB…")
    db = _get_db()
    try:
        for media_type in ("movie", "tv"):
            url = f"https://api.themoviedb.org/3/trending/{media_type}/week"
            try:
                resp = http_requests.get(
                    url,
                    params={"api_key": _TMDB_API_KEY},
                    timeout=10,
                )
                resp.raise_for_status()
            except Exception as fetch_exc:
                msg = f"TMDB trending fetch failed for {media_type}: {fetch_exc}"
                logger.warning(msg)
                stats["errors"].append(msg)
                continue

            for rank, item in enumerate(resp.json().get("results", [])[:20], start=1):
                tmdb_id = item.get("id")
                if not tmdb_id:
                    continue
                try:
                    record = (
                        db.query(Media)
                        .filter(Media.tmdb_id == int(tmdb_id))
                        .first()
                    )
                    if record is None:
                        continue
                    record.popularity      = float(item.get("popularity", record.popularity or 0))
                    record.trending_rank   = rank
                    record.trending_updated_at = datetime.now(timezone.utc)
                    stats["trending_updated"] += 1
                except Exception as db_exc:
                    logger.warning("DB update failed for tmdb_id=%s: %s", tmdb_id, db_exc)
                    stats["errors"].append(str(db_exc))

        db.commit()
        logger.info("[Phase 1] Committed trending updates for %d titles.", stats["trending_updated"])

    except Exception as phase1_exc:
        db.rollback()
        logger.error("[Phase 1] Fatal error: %s", phase1_exc)
        stats["errors"].append(f"phase1_fatal: {phase1_exc}")
        raise self.retry(exc=phase1_exc)
    finally:
        db.close()

    # ── Phase 2: Cache bust ───────────────────────────────────────────────────
    logger.info("[Phase 2] Busting Redis watch-provider cache for top %d titles…", _TOP_N_TITLES)
    rc = _get_redis()
    db = _get_db()
    top_titles = []
    try:
        top_titles = (
            db.query(Media)
            .filter(Media.popularity.isnot(None))
            .order_by(Media.popularity.desc())
            .limit(_TOP_N_TITLES)
            .all()
        )
    finally:
        db.close()

    if rc is not None:
        for media in top_titles:
            tmdb_id   = getattr(media, "tmdb_id", None)
            media_type = getattr(media, "media_type", "movie") or "movie"
            if not tmdb_id:
                continue
            try:
                # Pattern: providers:{type}:{id}:* — delete all region variants
                pattern = f"providers:{media_type}:{tmdb_id}:*"
                keys = rc.keys(pattern)
                if keys:
                    rc.delete(*keys)
                    stats["cache_busted"] += len(keys)
            except Exception as bust_exc:
                logger.warning("Cache bust failed for tmdb_id=%s: %s", tmdb_id, bust_exc)
        logger.info("[Phase 2] Busted %d provider cache keys.", stats["cache_busted"])
    else:
        logger.warning("[Phase 2] Redis unavailable — skipping cache bust.")

    # ── Phase 3: Cache pre-warm  ──────────────────────────────────────────────
    logger.info("[Phase 3] Pre-warming watch-provider cache for %d titles…", len(top_titles))
    _DEFAULT_REGIONS = ["US", "IN", "GB", "CA", "AU"]
    _PROVIDER_TTL    = 86_400   # 24 hours — matches rag_engine.py

    for media in top_titles:
        tmdb_id    = getattr(media, "tmdb_id", None)
        media_type = getattr(media, "media_type", "movie") or "movie"
        if not tmdb_id:
            continue

        endpoint = "movie" if media_type == "movie" else "tv"
        url      = f"https://api.themoviedb.org/3/{endpoint}/{tmdb_id}/watch/providers"
        try:
            resp = http_requests.get(
                url,
                params={"api_key": _TMDB_API_KEY},
                timeout=5,
            )
            if resp.status_code != 200:
                continue

            results = resp.json().get("results", {})

            # Write ONE cache key per region so any subset requested by the
            # frontend gets a full hit (matches get_watch_providers mget logic).
            for region in _DEFAULT_REGIONS:
                region_data = results.get(region, {})
                region_providers: list = []
                seen: set = set()

                for stream_type in ("flatrate", "free", "ads", "rent", "buy"):
                    for p in region_data.get(stream_type, []):
                        name = p.get("provider_name", "").strip()
                        if not name:
                            continue
                        key = (name, stream_type)
                        if key not in seen:
                            seen.add(key)
                            region_providers.append({
                                "provider":   name,
                                "type":       stream_type,
                                "region":     region,
                                "logo_path":  p.get("logo_path"),
                                "source":     "TMDB Watch Providers",
                            })

                if rc is not None:
                    cache_key = f"providers:{media_type}:{tmdb_id}:{region}"
                    try:
                        rc.setex(cache_key, _PROVIDER_TTL, json.dumps(region_providers))
                    except Exception as w_exc:
                        logger.warning("Cache write failed for %s: %s", cache_key, w_exc)

            stats["cache_warmed"] += 1

        except Exception as warm_exc:
            logger.warning("Pre-warm failed for tmdb_id=%s: %s", tmdb_id, warm_exc)

    logger.info("[Phase 3] Pre-warmed %d titles (%d regions each).", stats["cache_warmed"], len(_DEFAULT_REGIONS))


    # ── Summary ───────────────────────────────────────────────────────────────
    stats["finished_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("[update_trending_and_providers] DONE: %s", json.dumps(stats))
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# Task 2 — Weekly: full dataset ingestion + FAISS / pgvector index rebuild
# ═══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    name="celery_tasks.full_data_ingest",
    bind=True,
    max_retries=1,
    default_retry_delay=600,
    time_limit=7200,          # 2-hour hard limit — embedding 10k docs is slow
    soft_time_limit=6900,
    acks_late=True,
)
def full_data_ingest(self) -> dict[str, Any]:
    """
    Weekly periodic task (Sundays 02:00 UTC):

    1. Instantiates TMDBDataCollector and collects the latest comprehensive
       dataset (movies + TV, up to 10 000 titles).
    2. Saves the result to data/enhanced_dataset.csv (overwrite).
    3. Delegates to data_ingestor.DataIngestor.create_faiss_index() to rebuild
       the FAISS vector search index from the fresh CSV.

    This task is intentionally separate from the daily lightweight task — it
    is expensive (network I/O + embedding inference) and only needs to run once
    a week to incorporate new releases.
    """
    import importlib.util

    logger.info("[full_data_ingest] Starting weekly data collection…")
    start = datetime.now(timezone.utc).isoformat()

    if not _TMDB_API_KEY:
        return {"status": "error", "reason": "TMDB_API_KEY missing", "started_at": start}

    # ── Step 1: Collect dataset via TMDBDataCollector ─────────────────────────
    try:
        from tmdb_data_collector import TMDBDataCollector
        collector = TMDBDataCollector(api_key=_TMDB_API_KEY)
        df = collector.collect_comprehensive_dataset(target_size=10_000)
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "data", "enhanced_dataset.csv",
        )
        collector.save_dataset(df, output_path=output_path)
        logger.info("[full_data_ingest] Collected %d titles, saved to %s", len(df), output_path)
    except Exception as collect_exc:
        logger.error("[full_data_ingest] Collection failed: %s", collect_exc)
        raise self.retry(exc=collect_exc)

    # ── Step 2: Rebuild FAISS index ───────────────────────────────────────────
    try:
        ingestor_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data_ingestor.py"
        )
        spec = importlib.util.spec_from_file_location("data_ingestor", ingestor_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            mod.DataIngestor().create_faiss_index()
            logger.info("[full_data_ingest] FAISS index rebuilt successfully.")
    except Exception as ingest_exc:
        logger.warning("[full_data_ingest] FAISS rebuild failed (non-fatal): %s", ingest_exc)

    result = {
        "status": "ok",
        "started_at": start,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "titles_collected": len(df),
    }
    logger.info("[full_data_ingest] DONE: %s", json.dumps(result))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Task 3 — Every 5 minutes: train ALS model and publish factors to Redis
# ═══════════════════════════════════════════════════════════════════════════════

_ALS_REDIS_KEY = "als_model:v1"    # must match AdvancedRecommendationEngine.ALS_REDIS_KEY
_ALS_TTL       = 600               # 10 minutes — 2x the schedule interval, so a slow
                                   # train never leaves workers with a stale/missing key

@celery_app.task(
    name="celery_tasks.train_als_model_task",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    time_limit=240,       # 4-minute hard kill — training should be well under 1 min
    soft_time_limit=180,
    acks_late=True,
)
def train_als_model_task(self) -> dict[str, Any]:
    """
    Periodic task (every 5 minutes): train an ALS collaborative-filtering
    model on ALL user interactions, then serialise the resulting latent-factor
    arrays into Redis so every Uvicorn worker can read them without training.

    Redis key : ``als_model:v1``  (matches AdvancedRecommendationEngine.ALS_REDIS_KEY)
    TTL       : 600 s (10 minutes) — refreshed on every successful run

    Payload schema (pickled dict)
    -----------------------------
    {
        "user_factors" : np.ndarray  shape (n_users, k),
        "item_factors" : np.ndarray  shape (n_items, k),
        "user2idx"     : Dict[str, int],
        "item2idx"     : Dict[str, int],
        "trained_at"   : str  (ISO-8601 UTC),
        "n_users"      : int,
        "n_items"      : int,
        "factors"      : int,
    }

    Design notes
    ------------
    * All heavy imports (implicit, scipy, database) stay inside the function body
      so the module loads instantly and Celery Beat can import it without the
      full ML stack initialised.
    * If the interaction table has fewer than 2 users or 2 items the task exits
      cleanly without writing to Redis — scoring methods will continue to return
      0.5 (neutral) until enough data accumulates.
    * ALS factors are stored as float32 numpy arrays; pickle is safe here
      because the payload is produced and consumed by this same codebase.
    """
    import scipy.sparse as sp
    import numpy as np
    from collections import defaultdict

    try:
        from implicit.als import AlternatingLeastSquares
    except ImportError:
        logger.warning("[train_als_model_task] implicit not installed — skipping.")
        return {"status": "skipped", "reason": "implicit not installed"}

    rc = _get_redis()
    if rc is None:
        logger.warning("[train_als_model_task] Redis unavailable — cannot store model.")
        return {"status": "skipped", "reason": "Redis unavailable"}

    start = datetime.now(timezone.utc)

    # ── Step 1: Fetch all interactions from the database ──────────────────────
    from backend.database import Interaction
    db = _get_db()
    _RATING_MAP = {"like": 4.0, "love": 5.0, "watch": 3.5,
                   "dislike": 1.0, "skip": 2.0}
    try:
        interactions = db.query(Interaction).all()
    finally:
        db.close()

    if not interactions:
        logger.info("[train_als_model_task] No interactions found — skipping.")
        return {"status": "skipped", "reason": "no interactions"}

    # ── Step 2: Build user-item rating matrix ─────────────────────────────────
    user_item: dict = defaultdict(dict)
    for row in interactions:
        uid  = str(getattr(row, "user_id",  None) or "")
        iid  = str(getattr(row, "tmdb_id",  None) or getattr(row, "media_id", None) or "")
        itype = getattr(row, "interaction_type", "watch") or "watch"
        explicit = getattr(row, "rating", None)
        if not uid or not iid:
            continue
        if itype == "rate" and explicit:
            rating = float(explicit) / 2.0  # 1-10 scale → 0.5-5.0
        else:
            rating = _RATING_MAP.get(itype, 3.0)
        # Keep the highest rating if a user interacted with the same item multiple times
        if iid not in user_item[uid] or user_item[uid][iid] < rating:
            user_item[uid][iid] = rating

    user_ids = sorted(user_item.keys())
    item_ids = sorted({iid for ratings in user_item.values() for iid in ratings})

    n_users, n_items = len(user_ids), len(item_ids)
    if n_users < 2 or n_items < 2:
        logger.info(
            "[train_als_model_task] Matrix too small (%d users, %d items) — skipping.",
            n_users, n_items,
        )
        return {"status": "skipped", "reason": "matrix too small",
                "n_users": n_users, "n_items": n_items}

    user2idx = {u: i for i, u in enumerate(user_ids)}
    item2idx = {it: i for i, it in enumerate(item_ids)}

    # Build item-major CSR (rows=items, cols=users) — shape implicit expects
    rows, cols, data = [], [], []
    for uid, ratings in user_item.items():
        u_idx = user2idx[uid]
        for iid, rating in ratings.items():
            rows.append(item2idx[iid])
            cols.append(u_idx)
            data.append(float(rating))

    csr_item_user = sp.csr_matrix(
        (data, (rows, cols)), shape=(n_items, n_users), dtype=np.float32
    )

    # ── Step 3: Train ALS ─────────────────────────────────────────────────────
    _FACTORS   = min(32, n_users - 1, n_items - 1)
    try:
        model = AlternatingLeastSquares(
            factors=_FACTORS,
            iterations=15,
            regularization=0.01,
            use_gpu=False,
            calculate_training_loss=False,
        )
        # implicit >= 0.7 fit() expects user x items matrix
        model.fit(csr_item_user.T.tocsr(), show_progress=False)
    except Exception as train_exc:
        logger.error("[train_als_model_task] ALS training failed: %s", train_exc)
        raise self.retry(exc=train_exc)

    # ── Step 4: Serialise and write to Redis ──────────────────────────────────
    payload = {
        "user_factors": np.array(model.user_factors, dtype=np.float32),
        "item_factors": np.array(model.item_factors, dtype=np.float32),
        "user2idx":     user2idx,
        "item2idx":     item2idx,
        "trained_at":   datetime.now(timezone.utc).isoformat(),
        "n_users":      n_users,
        "n_items":      n_items,
        "factors":      _FACTORS,
    }
    rc.setex(_ALS_REDIS_KEY, _ALS_TTL, pickle.dumps(payload, protocol=5))

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    result  = {
        "status":   "ok",
        "n_users":  n_users,
        "n_items":  n_items,
        "factors":  _FACTORS,
        "elapsed_s": round(elapsed, 2),
        "redis_key": _ALS_REDIS_KEY,
        "redis_ttl": _ALS_TTL,
    }
    logger.info("[train_als_model_task] DONE: %s", json.dumps(result))
    return result


# ── CLI entry-point ───────────────────────────────────────────────────────────
# Lets you quick-test a task without starting a full worker:
#   python celery_tasks.py
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Running update_trending_and_providers synchronously for testing…")
    result = update_trending_and_providers.apply().get()
    print("Result:", json.dumps(result, indent=2))
