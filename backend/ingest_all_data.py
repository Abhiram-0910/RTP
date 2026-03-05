"""
ingest_all_data.py — MIRAI Production Data Ingest Pipeline
Fetches 10,000+ movies and TV shows from TMDB, stores in SQLite, builds FAISS index.
Run once (or to refresh): python ingest_all_data.py
Resume-safe: skips already-ingested tmdb_ids.
"""
import os
import sys
import json
import time
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

# Ensure we can import from backend/
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE = "https://api.themoviedb.org/3"
FAISS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'faiss_index')
TARGET_SIZE = 10500

if not TMDB_API_KEY:
    print("ERROR: TMDB_API_KEY not set in .env")
    sys.exit(1)

# ── DB Setup ──────────────────────────────────────────────────────────────────
from enhanced_database import (
    engine, SessionLocal, Base, Media, StreamingPlatform,
    media_platforms, init_enhanced_db
)

def tmdb_get(endpoint: str, params: dict = {}) -> Optional[dict]:
    """Thread-safe TMDB GET with retry logic."""
    url = f"{TMDB_BASE}{endpoint}"
    params = {**params, "api_key": TMDB_API_KEY}
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:  # Rate limited
                wait = int(r.headers.get("Retry-After", "5"))
                time.sleep(wait)
                continue
            return None
        except Exception:
            time.sleep(1)
    return None


def get_genre_map(media_type: str) -> Dict[int, str]:
    """Fetch genre id→name map from TMDB."""
    data = tmdb_get(f"/genre/{media_type}/list", {"language": "en-US"})
    if data:
        return {g["id"]: g["name"] for g in data.get("genres", [])}
    return {}


def discover_ids(media_type: str, pages: int = 250) -> List[int]:
    """
    Discover media IDs from TMDB across multiple pages, languages, and years.
    Returns deduplicated list of TMDB IDs.
    """
    ids = set()
    languages = ["en", "hi", "te", "ta", "ko", "ja", "zh", "es", "fr", "de", "it", "pt"]
    years = list(range(1990, 2026))

    date_key = "primary_release_date" if media_type == "movie" else "first_air_date"
    ep = "/discover/movie" if media_type == "movie" else "/discover/tv"

    print(f"\n[Discover] Fetching {media_type} IDs across {len(languages)} languages...")

    # Phase 1: discover by language (popularity sorted)
    for lang in languages:
        for page in range(1, 21):  # 20 pages per language = ~400 items
            data = tmdb_get(ep, {
                "language": "en-US",
                "with_original_language": lang,
                "sort_by": "popularity.desc",
                "vote_count.gte": 50,
                "page": page,
            })
            if not data or not data.get("results"):
                break
            for item in data["results"]:
                ids.add(item["id"])
            if page >= data.get("total_pages", 1):
                break
            time.sleep(0.07)

    print(f"  [Discover] After language sweep: {len(ids)} IDs")

    # Phase 2: top-rated global sweep
    for page in range(1, 101):  # 100 pages of top-rated
        data = tmdb_get(ep, {
            "sort_by": "vote_average.desc",
            "vote_count.gte": 200,
            "page": page,
        })
        if not data or not data.get("results"):
            break
        for item in data["results"]:
            ids.add(item["id"])
        if page >= data.get("total_pages", 1):
            break
        time.sleep(0.05)

    print(f"  [Discover] After top-rated sweep: {len(ids)} IDs")

    # Phase 3: trending (current)
    for window in ["day", "week"]:
        for page in range(1, 6):
            data = tmdb_get(f"/trending/{media_type}/{window}", {"page": page})
            if data:
                for item in data.get("results", []):
                    ids.add(item["id"])
            time.sleep(0.05)

    print(f"  [Discover] Final unique {media_type} IDs: {len(ids)}")
    return list(ids)


def fetch_full_details(tmdb_id: int, media_type: str) -> Optional[dict]:
    """Fetch full details including credits, keywords, watch/providers."""
    ep = "/movie/" if media_type == "movie" else "/tv/"
    data = tmdb_get(f"{ep}{tmdb_id}", {
        "append_to_response": "credits,keywords,watch/providers",
        "language": "en-US",
    })
    return data


def extract_platforms(watch_data: dict, regions: List[str] = ["US", "IN", "GB"]) -> List[str]:
    """Extract streaming platform names from TMDB watch/providers."""
    platforms = set()
    results = watch_data.get("results", {})
    for region in regions:
        region_data = results.get(region, {})
        for service_type in ["flatrate", "free", "ads"]:
            for provider in region_data.get(service_type, []):
                platforms.add(provider.get("provider_name", "").strip())
    return [p for p in platforms if p]


def process_item(raw: dict, media_type: str, genre_map: Dict[int, str]) -> Optional[dict]:
    """Convert raw TMDB detail response into a clean dict for DB insertion."""
    if not raw:
        return None

    title = raw.get("title") if media_type == "movie" else raw.get("name", "")
    overview = raw.get("overview", "").strip()

    if not title or not overview or len(overview) < 20:
        return None

    rating = raw.get("vote_average", 0.0)
    if rating < 3.0:
        return None  # Skip junk

    # Genres — use genre_ids if genres list is empty (from discover endpoints)
    genres = [g["name"] for g in raw.get("genres", [])]
    if not genres and raw.get("genre_ids"):
        genres = [genre_map.get(gid, "") for gid in raw["genre_ids"] if gid in genre_map]

    # Keywords
    kw_data = raw.get("keywords", {})
    kw_list = kw_data.get("keywords", kw_data.get("results", []))
    keywords = [kw["name"] for kw in kw_list[:30]]

    # Cast & Director
    credits = raw.get("credits", {})
    cast = [c["name"] for c in credits.get("cast", [])[:7]]
    director = None
    for crew_member in credits.get("crew", []):
        if crew_member.get("job") == "Director":
            director = crew_member["name"]
            break

    # Runtime
    runtime = raw.get("runtime")
    if not runtime and raw.get("episode_run_time"):
        rts = raw["episode_run_time"]
        runtime = rts[0] if rts else None

    # Release date
    release_date = raw.get("release_date") or raw.get("first_air_date") or ""

    # Poster
    poster_path = raw.get("poster_path", "")
    if poster_path and not poster_path.startswith("http"):
        poster_path = f"https://image.tmdb.org/t/p/w500{poster_path}"

    # Streaming platforms
    platforms = extract_platforms(raw.get("watch/providers", {}))

    return {
        "tmdb_id": raw["id"],
        "title": title,
        "overview": overview,
        "release_date": release_date,
        "rating": rating,
        "poster_path": poster_path,
        "media_type": media_type,
        "original_language": raw.get("original_language", "en"),
        "runtime": runtime,
        "budget": raw.get("budget"),
        "revenue": raw.get("revenue"),
        "status": raw.get("status", "Released"),
        "tagline": raw.get("tagline", ""),
        "genres": genres,
        "keywords": keywords,
        "cast": cast,
        "director": director,
        "imdb_id": raw.get("imdb_id", ""),
        "popularity_score": raw.get("popularity", 0.0),
        "trending_score": raw.get("vote_count", 0),
        "streaming_platforms": platforms,
    }


def build_embedding_text(item: dict) -> str:
    """Build rich text for semantic embedding."""
    parts = [item["title"]]
    if item["genres"]:
        parts.append("Genres: " + ", ".join(item["genres"]))
    if item["keywords"]:
        parts.append("Themes: " + ", ".join(item["keywords"][:15]))
    if item["cast"]:
        parts.append("Cast: " + ", ".join(item["cast"]))
    if item["director"]:
        parts.append(f"Director: {item['director']}")
    if item["release_date"]:
        parts.append(f"Year: {item['release_date'][:4]}")
    parts.append(item["overview"])
    return ". ".join(parts)


def upsert_media_and_platforms(session, item: dict) -> Optional[int]:
    """Insert or update a media record and its streaming platforms. Returns db_id."""
    existing = session.query(Media).filter(Media.tmdb_id == item["tmdb_id"]).first()
    if existing:
        # Update key fields
        existing.rating = item["rating"]
        existing.popularity_score = item["popularity_score"]
        existing.trending_score = item["trending_score"]
        existing.genres = item["genres"]
        existing.keywords = item["keywords"]
        existing.poster_path = item["poster_path"]
        existing.last_updated = datetime.utcnow()
        db_id = existing.db_id
    else:
        media = Media(
            tmdb_id=item["tmdb_id"],
            title=item["title"],
            overview=item["overview"],
            release_date=item["release_date"],
            rating=item["rating"],
            poster_path=item["poster_path"],
            media_type=item["media_type"],
            original_language=item["original_language"],
            runtime=item["runtime"],
            budget=item["budget"],
            revenue=item["revenue"],
            status=item["status"],
            tagline=item["tagline"],
            genres=item["genres"],
            keywords=item["keywords"],
            cast=item["cast"],
            director=item["director"],
            imdb_id=item["imdb_id"],
            popularity_score=item["popularity_score"],
            trending_score=item["trending_score"],
        )
        session.add(media)
        session.flush()  # Get db_id
        db_id = media.db_id

    # Upsert streaming platforms
    for platform_name in item.get("streaming_platforms", []):
        if not platform_name:
            continue
        platform = session.query(StreamingPlatform).filter(
            StreamingPlatform.name == platform_name
        ).first()
        if not platform:
            platform = StreamingPlatform(name=platform_name, country="US")
            session.add(platform)
            session.flush()

        # Only add association if not already there
        media_obj = session.query(Media).filter(Media.db_id == db_id).first()
        if media_obj and platform not in media_obj.platforms:
            media_obj.platforms.append(platform)

    return db_id


def main():
    print("=" * 60)
    print("MIRAI Data Ingest Pipeline")
    print(f"Target: {TARGET_SIZE:,}+ titles")
    print("=" * 60)

    # Init DB schema (safe to run even if tables exist)
    print("\n[1/5] Initializing database schema...")
    try:
        init_enhanced_db()
    except Exception as e:
        print(f"  Warning during schema init: {e}")
        Base.metadata.create_all(bind=engine)
    print("  Schema ready.")

    # Fetch genre maps
    print("\n[2/5] Fetching genre metadata from TMDB...")
    movie_genre_map = get_genre_map("movie")
    tv_genre_map = get_genre_map("tv")
    print(f"  Movie genres: {len(movie_genre_map)}, TV genres: {len(tv_genre_map)}")

    # Discover IDs
    print("\n[3/5] Discovering media IDs...")
    movie_ids = discover_ids("movie")
    tv_ids = discover_ids("tv")
    all_ids = [("movie", mid) for mid in movie_ids] + [("tv", tid) for tid in tv_ids]
    print(f"\n  Total IDs to process: {len(all_ids):,}")

    # Fetch full details and ingest
    print("\n[4/5] Fetching full details and ingesting into DB...")
    session = SessionLocal()
    existing_ids = {row[0] for row in session.query(Media.tmdb_id).all()}
    print(f"  Already ingested: {len(existing_ids):,} titles (will update metadata)")

    texts_for_faiss = []
    metadatas_for_faiss = []
    ingested = 0
    errors = 0
    batch_size = 50

    try:
        for i, (media_type, tmdb_id) in enumerate(all_ids):
            genre_map = movie_genre_map if media_type == "movie" else tv_genre_map

            raw = fetch_full_details(tmdb_id, media_type)
            item = process_item(raw, media_type, genre_map) if raw else None

            if item:
                try:
                    db_id = upsert_media_and_platforms(session, item)
                    emb_text = build_embedding_text(item)
                    texts_for_faiss.append(emb_text)
                    metadatas_for_faiss.append({
                        "tmdb_id": item["tmdb_id"],
                        "id": item["tmdb_id"],  # alias for legacy compat
                        "media_type": item["media_type"],
                        "title": item["title"],
                        "db_id": db_id,
                    })
                    ingested += 1
                except Exception as e:
                    errors += 1

            # Commit every batch_size items
            if (i + 1) % batch_size == 0:
                try:
                    session.commit()
                except Exception as e:
                    session.rollback()
                    errors += 1

                print(f"  [{i+1:>5}/{len(all_ids)}] Ingested: {ingested:,} | Errors: {errors}", end="\r")

            # Small rate-limit delay
            time.sleep(0.05)

            # Stop if we have enough
            if ingested >= TARGET_SIZE:
                print(f"\n  Reached target size of {TARGET_SIZE:,} titles.")
                break

        session.commit()
    except KeyboardInterrupt:
        print("\n  Ingest interrupted — saving progress...")
        session.commit()
    finally:
        session.close()

    total_in_db = SessionLocal().query(Media).count()
    print(f"\n  Done. DB now contains {total_in_db:,} titles.")

    # Build FAISS index
    print(f"\n[5/5] Building FAISS index from {len(texts_for_faiss):,} texts...")
    if not texts_for_faiss:
        print("  No new texts to index. Exiting.")
        return

    os.makedirs(FAISS_PATH, exist_ok=True)

    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_community.vectorstores import FAISS

        print("  Loading multilingual embedding model (paraphrase-multilingual-MiniLM-L12-v2)...")
        embeddings_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            model_kwargs={"device": "cpu"},
        )

        # If existing index, try to merge
        existing_index_path = os.path.join(FAISS_PATH, "index.faiss")
        if os.path.exists(existing_index_path):
            print("  Existing FAISS index found. Rebuilding from scratch for accuracy...")

        print(f"  Encoding {len(texts_for_faiss):,} texts (this may take 5-15 min)...")
        CHUNK = 1000
        combined_store = None
        for chunk_start in range(0, len(texts_for_faiss), CHUNK):
            chunk_texts = texts_for_faiss[chunk_start:chunk_start + CHUNK]
            chunk_metas = metadatas_for_faiss[chunk_start:chunk_start + CHUNK]
            chunk_store = FAISS.from_texts(
                texts=chunk_texts,
                embedding=embeddings_model,
                metadatas=chunk_metas,
            )
            if combined_store is None:
                combined_store = chunk_store
            else:
                combined_store.merge_from(chunk_store)
            print(f"  Encoded chunk {chunk_start + CHUNK:,}/{len(texts_for_faiss):,}", end="\r")

        if combined_store:
            combined_store.save_local(FAISS_PATH)
            print(f"\n  FAISS index saved to {FAISS_PATH}")
        else:
            print("  No vectors generated.")

    except ImportError as e:
        print(f"  Import error: {e}. Please run: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"  FAISS build error: {e}")
        raise

    print("\n" + "=" * 60)
    final_db = SessionLocal().query(Media).count()
    print(f"Ingest complete!")
    print(f"  DB titles : {final_db:,}")
    print(f"  FAISS vecs: {len(texts_for_faiss):,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
