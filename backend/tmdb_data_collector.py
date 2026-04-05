"""
MIRAI — Async TMDB data collection script
=========================================

Collects movies and TV shows from TMDB, fetches streaming platform data,
generates sentence-transformer embeddings, and upserts everything into the
PostgreSQL ``media`` table.

Run standalone:
    python -m backend.tmdb_data_collector

Or directly:
    python backend/tmdb_data_collector.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()

TMDB_API_KEY: str = os.environ["TMDB_API_KEY"]
DATABASE_URL: str = os.environ["DATABASE_URL"]
TMDB_BASE_URL: str = "https://api.themoviedb.org/3"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MOVIE_PAGES: int = 500       # ~20 results/page → ~10 000 movies
TV_PAGES: int = 250          # ~20 results/page → ~5 000 shows
BATCH_SIZE: int = 50         # DB upsert batch
PROGRESS_EVERY: int = 500    # Print progress every N records
COUNTRY_CODE: str = "IN"     # Streaming providers country
EMBED_MODEL_NAME: str = "paraphrase-multilingual-MiniLM-L12-v2"
MAX_CAST: int = 3            # Top cast members to embed

# Additional TMDB endpoint sweeps to hit 10 000+ unique titles
MOVIE_TOP_RATED_PAGES: int = 200
MOVIE_NOW_PLAYING_PAGES: int = 50
MOVIE_UPCOMING_PAGES: int = 50
TV_TOP_RATED_PAGES: int = 200
# /discover/movie genre sweeps: genre_id → pages
DISCOVER_GENRE_PAGES: dict[int, int] = {
    28:    30,   # Action
    18:    30,   # Drama
    35:    30,   # Comedy
    53:    30,   # Thriller
    10749: 30,   # Romance
    878:   30,   # Sci-Fi
    27:    30,   # Horror
    16:    30,   # Animation
    9648:  30,   # Mystery
    80:    30,   # Crime
}


# ---------------------------------------------------------------------------
# Tenacity retry helpers
# ---------------------------------------------------------------------------

def _is_retryable(exc: BaseException) -> bool:
    """Retry on HTTP 429 (rate-limit) or 500 (server error)."""
    return (
        isinstance(exc, aiohttp.ClientResponseError)
        and exc.status in {429, 500}
    )


def _retrying():
    """Return a tenacity ``retry`` decorator configured per spec."""
    return retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )


# ---------------------------------------------------------------------------
# Raw data container
# ---------------------------------------------------------------------------

@dataclass
class RawMedia:
    tmdb_id: int
    title: str
    media_type: str          # "movie" or "tv"
    overview: str
    genres: list[str]
    cast_names: list[str]
    release_date: str
    vote_average: float
    popularity: float
    poster_path: str
    platforms: dict[str, list[str]]
    original_language: str = ""     # ISO 639-1 code from TMDB (e.g. 'hi', 'te', 'ta')
    original_title: str = ""        # Native-script title (e.g. Devanagari, Telugu script)
    text_for_embedding: str = field(default="", init=False)

    def build_embedding_text(self) -> None:
        genres_str = ", ".join(self.genres) if self.genres else "Unknown"
        cast_str = ", ".join(self.cast_names[:MAX_CAST]) if self.cast_names else "Unknown"
        # Prefer native-script title so the multilingual model sees actual script.
        # Falls back to romanized/English title if original_title is absent.
        display_title = self.original_title.strip() if self.original_title.strip() else self.title
        self.text_for_embedding = (
            f"{display_title}. "
            f"{self.overview}. "
            f"Genres: {genres_str}. "
            f"Cast: {cast_str}."
        ).strip()


# ---------------------------------------------------------------------------
# TMDB HTTP helpers
# ---------------------------------------------------------------------------

@_retrying()
async def _get_json(
    session: aiohttp.ClientSession,
    path: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Perform a single authenticated GET request against the TMDB API.
    Raises ``aiohttp.ClientResponseError`` on non-2xx responses so that
    tenacity can catch it via ``_is_retryable``.
    """
    base_params = {"api_key": TMDB_API_KEY, "language": "en-US"}
    if params:
        base_params.update(params)

    async with session.get(
        f"{TMDB_BASE_URL}{path}",
        params=base_params,
        raise_for_status=True,
    ) as resp:
        return await resp.json()


async def fetch_page(
    session: aiohttp.ClientSession,
    media_type: str,
    page: int,
) -> list[dict[str, Any]]:
    """Fetch one page of popular movies or TV shows."""
    data = await _get_json(session, f"/{media_type}/popular", {"page": page})
    return data.get("results", [])


async def fetch_credits(
    session: aiohttp.ClientSession,
    media_type: str,
    tmdb_id: int,
) -> list[str]:
    """Return the top ``MAX_CAST`` cast names for a title."""
    try:
        data = await _get_json(session, f"/{media_type}/{tmdb_id}/credits")
        cast = data.get("cast", [])
        return [m["name"] for m in cast[:MAX_CAST] if "name" in m]
    except Exception as exc:
        logger.debug("Credits fetch failed for %s %s: %s", media_type, tmdb_id, exc)
        return []


async def fetch_watch_providers(
    session: aiohttp.ClientSession,
    media_type: str,
    tmdb_id: int,
) -> dict[str, list[str]]:
    """
    Return a dict mapping country codes to flat-rate platform name lists.
    Only flatrate (subscription) providers are included.

    Example: {"IN": ["Netflix", "Amazon Prime Video"]}
    """
    try:
        data = await _get_json(session, f"/{media_type}/{tmdb_id}/watch/providers")
        results: dict[str, Any] = data.get("results", {})
        platforms: dict[str, list[str]] = {}
        for country, info in results.items():
            flatrate = info.get("flatrate", [])
            names = [p["provider_name"] for p in flatrate if "provider_name" in p]
            if names:
                platforms[country] = names
        return platforms
    except Exception as exc:
        logger.debug(
            "Watch providers fetch failed for %s %s: %s", media_type, tmdb_id, exc
        )
        return {}


# ---------------------------------------------------------------------------
# Genre ID → name mapping (fetched once at startup)
# ---------------------------------------------------------------------------

async def build_genre_map(session: aiohttp.ClientSession) -> dict[int, str]:
    """Build a combined genre-id → genre-name map for movies and TV shows."""
    genre_map: dict[int, str] = {}
    for media_type in ("movie", "tv"):
        try:
            data = await _get_json(session, f"/genre/{media_type}/list")
            for g in data.get("genres", []):
                genre_map[g["id"]] = g["name"]
        except Exception as exc:
            logger.warning("Could not load %s genres: %s", media_type, exc)
    return genre_map


# ---------------------------------------------------------------------------
# Page collection — movies and TV shows
# ---------------------------------------------------------------------------

async def _ingest_results(
    session: aiohttp.ClientSession,
    results: list[dict[str, Any]],
    media_type: str,
    genre_map: dict[int, str],
    all_items: list["RawMedia"],
    seen_ids: set[tuple[str, int]],
) -> None:
    """
    Process a single page of TMDB results, deduplicate by (media_type, tmdb_id),
    fetch credits + watch providers for each new title, and append to all_items.
    """
    for item in results:
        tmdb_id: int = item.get("id", 0)
        if not tmdb_id:
            continue
        key = (media_type, tmdb_id)
        if key in seen_ids:
            continue
        seen_ids.add(key)

        title = item.get("title") or item.get("name") or ""
        overview = item.get("overview") or ""
        release_date = (
            item.get("release_date") or item.get("first_air_date") or ""
        )
        vote_average = float(item.get("vote_average") or 0.0)
        popularity = float(item.get("popularity") or 0.0)
        poster_path = item.get("poster_path") or ""
        genre_ids: list[int] = item.get("genre_ids") or []
        genres = [genre_map.get(gid, "") for gid in genre_ids if gid in genre_map]

        cast_names, platforms = await asyncio.gather(
            fetch_credits(session, media_type, tmdb_id),
            fetch_watch_providers(session, media_type, tmdb_id),
        )

        raw = RawMedia(
            tmdb_id=tmdb_id,
            title=title,
            media_type=media_type,
            overview=overview,
            genres=genres,
            cast_names=cast_names,
            release_date=release_date,
            vote_average=vote_average,
            popularity=popularity,
            poster_path=poster_path,
            platforms=platforms,
        )
        raw.build_embedding_text()
        all_items.append(raw)

        total_so_far = len(all_items)
        if total_so_far % PROGRESS_EVERY == 0:
            logger.info("Collected %d unique titles so far …", total_so_far)


async def _sweep_endpoint(
    session: aiohttp.ClientSession,
    label: str,
    path: str,
    max_pages: int,
    media_type: str,
    genre_map: dict[int, str],
    all_items: list["RawMedia"],
    seen_ids: set[tuple[str, int]],
    extra_params: dict[str, Any] | None = None,
) -> None:
    """
    Generic helper: iterate ``max_pages`` pages of a TMDB list endpoint,
    using the same tenacity retry logic as ``fetch_page``.
    """
    logger.info("[sweep] %s — %d pages …", label, max_pages)
    for page in range(1, max_pages + 1):
        params: dict[str, Any] = {"page": page}
        if extra_params:
            params.update(extra_params)
        try:
            data = await _get_json(session, path, params)
            results = data.get("results", [])
        except Exception as exc:
            logger.warning("[sweep] %s page %d skipped after retries: %s", label, page, exc)
            continue
        await _ingest_results(session, results, media_type, genre_map, all_items, seen_ids)
        await asyncio.sleep(0.05)   # respect TMDB rate limit
    logger.info("[sweep] %s done. Running total: %d unique titles.", label, len(all_items))


async def collect_all_items(
    session: aiohttp.ClientSession,
    genre_map: dict[int, str],
) -> list[RawMedia]:
    """
    Collect 10,000+ unique movies and TV shows from TMDB by sweeping multiple
    endpoints and genre-filtered discover queries.

    Sweep plan
    ----------
    Movies
      - /movie/popular        500 pages  (~10 000 raw results)
      - /movie/top_rated      200 pages  (high-quality back-catalogue)
      - /movie/now_playing     50 pages  (theatrical releases)
      - /movie/upcoming        50 pages  (unreleased / pre-release)
      - /discover/movie       10 genres × 30 pages (genre diversity)

    TV Shows
      - /tv/popular           250 pages
      - /tv/top_rated         200 pages

    All results are deduplicated by (media_type, tmdb_id) so overlapping
    titles across endpoints are counted only once.
    """
    all_items: list[RawMedia] = []
    seen_ids: set[tuple[str, int]] = set()

    # ── Movie sweeps ─────────────────────────────────────────────────────────
    await _sweep_endpoint(
        session, "movie/popular", "/movie/popular",
        MOVIE_PAGES, "movie", genre_map, all_items, seen_ids,
    )
    await _sweep_endpoint(
        session, "movie/top_rated", "/movie/top_rated",
        MOVIE_TOP_RATED_PAGES, "movie", genre_map, all_items, seen_ids,
    )
    await _sweep_endpoint(
        session, "movie/now_playing", "/movie/now_playing",
        MOVIE_NOW_PLAYING_PAGES, "movie", genre_map, all_items, seen_ids,
    )
    await _sweep_endpoint(
        session, "movie/upcoming", "/movie/upcoming",
        MOVIE_UPCOMING_PAGES, "movie", genre_map, all_items, seen_ids,
    )

    # ── Discover sweeps (genre-filtered) ─────────────────────────────────────
    for genre_id, pages in DISCOVER_GENRE_PAGES.items():
        genre_name = genre_map.get(genre_id, str(genre_id))
        await _sweep_endpoint(
            session, f"discover/movie genre={genre_name}", "/discover/movie",
            pages, "movie", genre_map, all_items, seen_ids,
            extra_params={"with_genres": genre_id, "sort_by": "popularity.desc"},
        )

    # ── TV sweeps ─────────────────────────────────────────────────────────────
    await _sweep_endpoint(
        session, "tv/popular", "/tv/popular",
        TV_PAGES, "tv", genre_map, all_items, seen_ids,
    )
    await _sweep_endpoint(
        session, "tv/top_rated", "/tv/top_rated",
        TV_TOP_RATED_PAGES, "tv", genre_map, all_items, seen_ids,
    )

    logger.info("Collection complete. Total unique titles: %d", len(all_items))
    return all_items


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

def generate_embeddings(
    model: SentenceTransformer,
    items: list[RawMedia],
) -> list[list[float]]:
    """
    Generate 384-dim embeddings for all items using the provided model.
    Done in one batch call (sentence-transformers handles internal batching).
    """
    texts = [item.text_for_embedding for item in items]
    logger.info("Generating embeddings for %d texts …", len(texts))
    vectors = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,   # L2-normalise → cosine via dot product
        convert_to_numpy=True,
    )
    logger.info("Embedding generation complete.")
    return [v.tolist() for v in vectors]


# ---------------------------------------------------------------------------
# Popularity normalisation (min-max across the full batch)
# ---------------------------------------------------------------------------

def normalize_popularity(items: list[RawMedia]) -> list[float]:
    """Return min-max normalised popularity scores in [0, 1]."""
    scores = [item.popularity for item in items]
    min_pop = min(scores) if scores else 0.0
    max_pop = max(scores) if scores else 1.0
    span = max_pop - min_pop or 1.0
    return [(s - min_pop) / span for s in scores]


# ---------------------------------------------------------------------------
# Database upsert
# ---------------------------------------------------------------------------

async def upsert_batch(
    db_session: AsyncSession,
    batch: list[dict[str, Any]],
) -> None:
    """
    Upsert a batch of media records using PostgreSQL ON CONFLICT DO UPDATE.
    Conflict target: ``tmdb_id`` (unique column).
    """
    stmt = pg_insert(MediaTable).values(batch)
    stmt = stmt.on_conflict_do_update(
        index_elements=["tmdb_id"],
        set_={
            "title": stmt.excluded.title,
            "media_type": stmt.excluded.media_type,
            "overview": stmt.excluded.overview,
            "genres": stmt.excluded.genres,
            "cast_names": stmt.excluded.cast_names,
            "release_date": stmt.excluded.release_date,
            "vote_average": stmt.excluded.vote_average,
            "popularity": stmt.excluded.popularity,
            "poster_path": stmt.excluded.poster_path,
            "platforms": stmt.excluded.platforms,
            "embedding": stmt.excluded.embedding,
        },
    )
    await db_session.execute(stmt)
    await db_session.commit()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    """
    Orchestrates the full ingest pipeline:

    1. Load env / model.
    2. Collect all TMDB pages (with credits + watch providers).
    3. Generate embeddings.
    4. Normalise popularity scores.
    5. Upsert into PostgreSQL in batches of ``BATCH_SIZE``.
    """
    # ------------------------------------------------------------------
    # 1. Embedding model (loaded once — CPU friendly, ~280 MB RAM)
    # ------------------------------------------------------------------
    logger.info("Loading embedding model: %s", EMBED_MODEL_NAME)
    model = SentenceTransformer(EMBED_MODEL_NAME)

    # ------------------------------------------------------------------
    # 2. DB engine (no pgvector extension needed at ingest time — already
    #    created by init_db() on app startup)
    # ------------------------------------------------------------------
    engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Lazy-import the ORM table object to avoid circular deps when running
    # as a standalone script vs. as part of the FastAPI app.
    global MediaTable  # noqa: PLW0603
    try:
        from backend.enhanced_database import Media  # FastAPI app context
        MediaTable = Media.__table__
    except ImportError:
        from backend.enhanced_database import Media  # standalone execution
        MediaTable = Media.__table__

    # ------------------------------------------------------------------
    # 3. Collection
    # ------------------------------------------------------------------
    connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=30, connect=10)

    async with aiohttp.ClientSession(
        connector=connector, timeout=timeout
    ) as http_session:
        genre_map = await build_genre_map(http_session)
        logger.info("Genre map loaded: %d genres", len(genre_map))

        all_items = await collect_all_items(http_session, genre_map)

    if not all_items:
        logger.error("No items collected — aborting.")
        await engine.dispose()
        return

    # ------------------------------------------------------------------
    # 4. Embeddings
    # ------------------------------------------------------------------
    embeddings = generate_embeddings(model, all_items)

    # ------------------------------------------------------------------
    # 5. Popularity normalisation
    # ------------------------------------------------------------------
    norm_popularity = normalize_popularity(all_items)

    # ------------------------------------------------------------------
    # 6. Upsert in batches
    # ------------------------------------------------------------------
    total = len(all_items)
    logger.info("Upserting %d records into PostgreSQL (batch size=%d) …", total, BATCH_SIZE)

    processed = 0
    async with session_factory() as db_session:
        for start in range(0, total, BATCH_SIZE):
            end = min(start + BATCH_SIZE, total)
            batch_items = all_items[start:end]
            batch_embeddings = embeddings[start:end]
            batch_norm_pop = norm_popularity[start:end]

            batch_rows: list[dict[str, Any]] = []
            for item, emb, norm_pop in zip(batch_items, batch_embeddings, batch_norm_pop):
                batch_rows.append(
                    {
                        "tmdb_id": item.tmdb_id,
                        "title": item.title,
                        "media_type": item.media_type,
                        "overview": item.overview,
                        "genres": item.genres,
                        "cast_names": item.cast_names,
                        "release_date": item.release_date,
                        "vote_average": item.vote_average,
                        "popularity": norm_pop,   # store normalised value
                        "poster_path": item.poster_path,
                        "platforms": item.platforms,
                        "embedding": emb,
                    }
                )

            try:
                await upsert_batch(db_session, batch_rows)
            except Exception as exc:
                logger.error("Upsert failed for batch %d–%d: %s", start, end, exc)
                await db_session.rollback()
                continue

            processed += len(batch_rows)
            if processed % PROGRESS_EVERY == 0 or processed == total:
                logger.info("Processed %d/%d …", processed, total)

    logger.info("Ingest complete. %d/%d records upserted.", processed, total)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Regional content sweep — Hindi / Telugu / Tamil
# ---------------------------------------------------------------------------

# Sweep plan: (language_code, endpoint, sort_by, n_pages, label)
_REGIONAL_SWEEPS: list[tuple[str, str, str, int, str]] = [
    # Hindi movies
    ("hi", "/discover/movie", "popularity.desc",   100, "Bollywood/Popular"),
    ("hi", "/discover/movie", "vote_average.desc",  50, "Bollywood/TopRated"),
    ("hi", "/discover/tv",   "popularity.desc",    50, "Hindi TV/Popular"),
    # Telugu movies
    ("te", "/discover/movie", "popularity.desc",   80, "Tollywood/Popular"),
    ("te", "/discover/movie", "vote_average.desc",  40, "Tollywood/TopRated"),
    ("te", "/discover/tv",   "popularity.desc",    30, "Telugu TV/Popular"),
    # Tamil movies (bonus)
    ("ta", "/discover/movie", "popularity.desc",   50, "Kollywood/Popular"),
]


async def collect_regional_content(
    session: aiohttp.ClientSession,
    genre_map: dict[int, str],
    all_items: list[RawMedia],
    seen_ids: set[tuple[str, int]],
) -> None:
    """
    Sweep TMDB /discover endpoints for Hindi, Telugu, and Tamil content,
    requesting titles and overviews in the source language so the multilingual
    embedding model (paraphrase-multilingual-MiniLM-L12-v2) receives authentic
    native-script text rather than romanized or translated strings.

    Results are merged into the shared ``all_items`` list and ``seen_ids`` set
    so duplicates with the English sweep are automatically discarded.

    Each ``RawMedia`` item produced here has ``original_language`` set to the
    ISO 639-1 code (e.g. ``'hi'``, ``'te'``, ``'ta'``) so the DB column
    ``media_language`` can be populated and later used for frontend filtering.
    """
    for lang_code, path, sort_by, n_pages, label in _REGIONAL_SWEEPS:
        logger.info(
            "[regional] %s (%s) — %d pages, sort=%s …",
            label, lang_code, n_pages, sort_by,
        )
        for page in range(1, n_pages + 1):
            params: dict[str, Any] = {
                "page": page,
                "with_original_language": lang_code,
                "sort_by": sort_by,
                # Request TMDB metadata in the source language so titles /
                # overviews come back in native script where TMDB has them.
                "language": lang_code,
                "vote_count.gte": 10,   # filter out obscure zero-vote entries
            }

            # Determine media_type from path
            media_type = "tv" if "/discover/tv" in path else "movie"

            try:
                data = await _get_json(session, path, params)
                results = data.get("results", [])
            except Exception as exc:
                logger.warning(
                    "[regional] %s page %d skipped: %s", label, page, exc
                )
                await asyncio.sleep(0.1)
                continue

            for item in results:
                tmdb_id: int = item.get("id", 0)
                if not tmdb_id:
                    continue
                key = (media_type, tmdb_id)
                if key in seen_ids:
                    continue
                seen_ids.add(key)

                # Prefer native-script title; fall back to localized/English title
                original_title: str = (
                    item.get("original_title") or item.get("original_name") or ""
                ).strip()
                title: str = (
                    item.get("title") or item.get("name") or original_title
                ).strip()
                overview: str = (item.get("overview") or "").strip()
                release_date: str = (
                    item.get("release_date") or item.get("first_air_date") or ""
                )
                vote_average = float(item.get("vote_average") or 0.0)
                popularity    = float(item.get("popularity") or 0.0)
                poster_path: str = item.get("poster_path") or ""
                genre_ids: list[int] = item.get("genre_ids") or []
                genres = [
                    genre_map.get(gid, "")
                    for gid in genre_ids
                    if gid in genre_map
                ]

                cast_names, platforms = await asyncio.gather(
                    fetch_credits(session, media_type, tmdb_id),
                    fetch_watch_providers(session, media_type, tmdb_id),
                )

                raw = RawMedia(
                    tmdb_id=tmdb_id,
                    title=title,
                    media_type=media_type,
                    overview=overview,
                    genres=genres,
                    cast_names=cast_names,
                    release_date=release_date,
                    vote_average=vote_average,
                    popularity=popularity,
                    poster_path=poster_path,
                    platforms=platforms,
                    original_language=lang_code,
                    original_title=original_title,
                )
                raw.build_embedding_text()
                all_items.append(raw)

                total = len(all_items)
                if total % PROGRESS_EVERY == 0:
                    logger.info(
                        "[regional] Collected %d unique titles so far …", total
                    )

            await asyncio.sleep(0.05)   # stay within TMDB rate limit

        logger.info(
            "[regional] %s done. Running total: %d unique titles.",
            label, len(all_items),
        )

    logger.info(
        "[regional] All regional sweeps complete. Final unique titles: %d",
        len(all_items),
    )


async def main() -> None:
    """
    Full ingestion pipeline:
      1. English content (popular / top-rated / now-playing / upcoming / genre sweeps)
      2. Regional content (Hindi / Telugu / Tamil)
      3. Embed all unique titles and upsert into PostgreSQL.
    """
    # ------------------------------------------------------------------
    # 1. Embedding model (loaded once — CPU friendly, ~280 MB RAM)
    # ------------------------------------------------------------------
    logger.info("Loading embedding model: %s", EMBED_MODEL_NAME)
    model = SentenceTransformer(EMBED_MODEL_NAME)

    # ------------------------------------------------------------------
    # 2. DB engine (no pgvector extension needed at ingest time — already
    #    created by init_db() on app startup)
    # ------------------------------------------------------------------
    engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Lazy-import the ORM table object to avoid circular deps when running
    # as a standalone script vs. as part of the FastAPI app.
    global MediaTable  # noqa: PLW0603
    try:
        from backend.enhanced_database import Media  # FastAPI app context
        MediaTable = Media.__table__
    except ImportError:
        from backend.enhanced_database import Media  # standalone execution
        MediaTable = Media.__table__

    # ------------------------------------------------------------------
    # 3. Collection
    # ------------------------------------------------------------------
    connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=30, connect=10)

    async with aiohttp.ClientSession(
        connector=connector, timeout=timeout
    ) as http_session:
        genre_map = await build_genre_map(http_session)
        logger.info("Genre map loaded: %d genres", len(genre_map))

        all_items = await collect_all_items(http_session, genre_map)

    if not all_items:
        logger.error("No items collected — aborting.")
        await engine.dispose()
        return

    # ------------------------------------------------------------------
    # 4. Embeddings
    # ------------------------------------------------------------------
    embeddings = generate_embeddings(model, all_items)

    # ------------------------------------------------------------------
    # 5. Popularity normalisation
    # ------------------------------------------------------------------
    norm_popularity = normalize_popularity(all_items)

    # ------------------------------------------------------------------
    # 6. Upsert in batches
    # ------------------------------------------------------------------
    total = len(all_items)
    logger.info("Upserting %d records into PostgreSQL (batch size=%d) …", total, BATCH_SIZE)

    processed = 0
    async with session_factory() as db_session:
        for start in range(0, total, BATCH_SIZE):
            end = min(start + BATCH_SIZE, total)
            batch_items = all_items[start:end]
            batch_embeddings = embeddings[start:end]
            batch_norm_pop = norm_popularity[start:end]

            batch_rows: list[dict[str, Any]] = []
            for item, emb, norm_pop in zip(batch_items, batch_embeddings, batch_norm_pop):
                batch_rows.append(
                    {
                        "tmdb_id": item.tmdb_id,
                        "title": item.title,
                        "media_type": item.media_type,
                        "overview": item.overview,
                        "genres": item.genres,
                        "cast_names": item.cast_names,
                        "release_date": item.release_date,
                        "vote_average": item.vote_average,
                        "popularity": norm_pop,   # store normalised value
                        "poster_path": item.poster_path,
                        "platforms": item.platforms,
                        "embedding": emb,
                    }
                )

            try:
                await upsert_batch(db_session, batch_rows)
            except Exception as exc:
                logger.error("Upsert failed for batch %d–%d: %s", start, end, exc)
                await db_session.rollback()
                continue

            processed += len(batch_rows)
            if processed % PROGRESS_EVERY == 0 or processed == total:
                logger.info("Processed %d/%d …", processed, total)

    logger.info("Ingest complete. %d/%d records upserted.", processed, total)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())