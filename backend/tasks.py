"""
tasks.py — Optional Celery background tasks for Movie and TV Shows Recommending Engine.

Uses Redis as broker/backend. The app works WITHOUT Redis — all Celery
calls are wrapped in try/except so failures are silent and FastAPI's
built-in BackgroundTasks handle the same work as a fallback.

Setup (optional):
  # Windows — use Redis via Docker:
  docker run -d -p 6379:6379 redis:alpine

  # Then run the Celery worker:
  cd backend
  ..\\venv\\Scripts\\celery -A tasks worker --loglevel=info --pool=solo

Environment variable:  CELERY_BROKER_URL  (default: redis://localhost:6379/0)
"""

import os
from datetime import datetime

# ── Celery App Setup ──────────────────────────────────────────────────────────

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", BROKER_URL)

try:
    from celery import Celery

    celery_app = Celery(
        "mirai_tasks",
        broker=BROKER_URL,
        backend=RESULT_BACKEND,
        include=["tasks"],
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
    CELERY_AVAILABLE = True
except ImportError:
    celery_app = None
    CELERY_AVAILABLE = False
    print("[tasks] Celery not installed — background tasks will use FastAPI BackgroundTasks.")


def _is_celery_ready() -> bool:
    """Check if Celery + broker are reachable."""
    if not CELERY_AVAILABLE or celery_app is None:
        return False
    try:
        celery_app.control.ping(timeout=1)
        return True
    except Exception:
        return False


# ── Task: Refresh Trending Data from TMDB ─────────────────────────────────────

def _do_refresh_trending():
    """Core logic — shared by Celery task and inline fallback."""
    import os, requests as http_requests
    from dotenv import load_dotenv
    load_dotenv()

    TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
    if not TMDB_API_KEY:
        print("[tasks] TMDB_API_KEY not set — skipping trending refresh.")
        return

    try:
        from enhanced_database import get_db_session, Media, TrendingMedia
    except ImportError:
        print("[tasks] Could not import enhanced_database.")
        return

    db = get_db_session()
    try:
        for media_type in ["movie", "tv"]:
            url = f"https://api.themoviedb.org/3/trending/{media_type}/week"
            r = http_requests.get(url, params={"api_key": TMDB_API_KEY}, timeout=10)
            if r.status_code != 200:
                continue
            items = r.json().get("results", [])
            for rank, item in enumerate(items[:20], start=1):
                tmdb_id = item.get("id")
                if not tmdb_id:
                    continue
                media_record = db.query(Media).filter(Media.tmdb_id == int(tmdb_id)).first()
                if not media_record:
                    continue
                # Upsert TrendingMedia
                existing = db.query(TrendingMedia).filter(TrendingMedia.media_id == media_record.db_id).first()
                score = float(item.get("popularity", 0))
                if existing:
                    existing.trending_score = score
                    existing.rank_position = rank
                    existing.calculated_at = datetime.utcnow()
                else:
                    db.add(TrendingMedia(
                        media_id=media_record.db_id,
                        trending_score=score,
                        rank_position=rank,
                        category=media_type,
                        region="global",
                    ))
        db.commit()
        print(f"[tasks] Trending refresh complete at {datetime.utcnow().isoformat()}")
    except Exception as e:
        db.rollback()
        print(f"[tasks] Trending refresh error: {e}")
    finally:
        db.close()


if CELERY_AVAILABLE and celery_app is not None:
    @celery_app.task(name="tasks.refresh_trending", bind=True, max_retries=2, default_retry_delay=60)
    def refresh_trending_task(self):
        """Celery task: pull weekly trending from TMDB and upsert into DB."""
        try:
            _do_refresh_trending()
        except Exception as exc:
            raise self.retry(exc=exc)
else:
    def refresh_trending_task():  # type: ignore[misc]
        """Fallback stub when Celery is not available."""
        _do_refresh_trending()


# ── Task: Bulk Update Streaming Providers ─────────────────────────────────────

def _do_update_providers(tmdb_ids: list):
    """Core logic — shared by Celery task and inline fallback."""
    import os, requests as http_requests
    from dotenv import load_dotenv
    load_dotenv()

    TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
    if not TMDB_API_KEY:
        return

    try:
        from enhanced_database import get_db_session, Media, StreamingPlatform, media_platforms
    except ImportError:
        return

    db = get_db_session()
    try:
        for tmdb_id in tmdb_ids:
            media_record = db.query(Media).filter(Media.tmdb_id == int(tmdb_id)).first()
            if not media_record:
                continue
            ep = "movie" if media_record.media_type == "movie" else "tv"
            url = f"https://api.themoviedb.org/3/{ep}/{tmdb_id}/watch/providers"
            r = http_requests.get(url, params={"api_key": TMDB_API_KEY}, timeout=5)
            if r.status_code != 200:
                continue
            results = r.json().get("results", {})
            platforms_seen = set()
            for region in ["US", "IN", "GB"]:
                rd = results.get(region, {})
                for stype in ["flatrate", "free", "ads"]:
                    for p in rd.get(stype, []):
                        name = p.get("provider_name", "").strip()
                        if not name:
                            continue
                        platforms_seen.add(name)
                        existing_plat = db.query(StreamingPlatform).filter(StreamingPlatform.name == name).first()
                        if not existing_plat:
                            existing_plat = StreamingPlatform(name=name)
                            db.add(existing_plat)
                            db.flush()
                        if existing_plat not in media_record.platforms:
                            media_record.platforms.append(existing_plat)
        db.commit()
        print(f"[tasks] Provider update complete for {len(tmdb_ids)} titles.")
    except Exception as e:
        db.rollback()
        print(f"[tasks] Provider update error: {e}")
    finally:
        db.close()


if CELERY_AVAILABLE and celery_app is not None:
    @celery_app.task(name="tasks.update_providers", bind=True, max_retries=2, default_retry_delay=30)
    def update_provider_cache_task(self, tmdb_ids: list):
        """Celery task: bulk-update streaming providers for given TMDB IDs."""
        try:
            _do_update_providers(tmdb_ids)
        except Exception as exc:
            raise self.retry(exc=exc)
else:
    def update_provider_cache_task(tmdb_ids: list):  # type: ignore[misc]
        """Fallback stub."""
        _do_update_providers(tmdb_ids)


# ── Dispatcher Helpers ────────────────────────────────────────────────────────

def dispatch_refresh_trending():
    """Call from FastAPI: use Celery if available, else run inline."""
    if _is_celery_ready():
        refresh_trending_task.delay()  # type: ignore[union-attr]
    else:
        # Run synchronously in a thread via FastAPI BackgroundTasks caller
        _do_refresh_trending()


def dispatch_update_providers(tmdb_ids: list):
    """Call from FastAPI: use Celery if available, else run inline."""
    if _is_celery_ready():
        update_provider_cache_task.delay(tmdb_ids)  # type: ignore[union-attr]
    else:
        _do_update_providers(tmdb_ids)


# ── Task: Data Ingestion (FAISS index rebuild) ────────────────────────────────

def _do_ingest_data():
    """
    Core ingestion logic — rebuilds the FAISS vector index from CSV data.
    Shared by the Celery task and the inline BackgroundTasks fallback.
    """
    try:
        import sys
        import os
        # Ensure the backend directory is on sys.path when run as a task
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        from data_ingestor import DataIngestor
        print(f"[tasks] Starting FAISS data ingestion at {datetime.utcnow().isoformat()}")
        ingestor = DataIngestor()
        ingestor.create_faiss_index()
        print(f"[tasks] Data ingestion complete at {datetime.utcnow().isoformat()}")
    except Exception as e:
        print(f"[tasks] Data ingestion error: {e}")
        raise


if CELERY_AVAILABLE and celery_app is not None:
    @celery_app.task(name="tasks.ingest_data", bind=True, max_retries=1, default_retry_delay=120, time_limit=3600)
    def ingest_data_task(self):
        """
        Celery task: rebuild the FAISS index in the background.

        time_limit=3600 gives the worker up to 1 hour — embedding generation
        for thousands of documents is CPU-intensive.
        """
        try:
            _do_ingest_data()
        except Exception as exc:
            raise self.retry(exc=exc)
else:
    def ingest_data_task():  # type: ignore[misc]
        """Fallback stub when Celery is not available."""
        _do_ingest_data()


def dispatch_ingest_data():
    """
    Call from FastAPI: dispatch ingestion via Celery if the broker is reachable,
    otherwise run inline (will block the calling thread — use with BackgroundTasks).
    """
    if _is_celery_ready():
        ingest_data_task.delay()  # type: ignore[union-attr]
        print("[tasks] Ingestion dispatched to Celery worker.")
    else:
        print("[tasks] Celery unavailable — running ingestion inline.")
        _do_ingest_data()
