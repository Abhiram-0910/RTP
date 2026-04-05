import asyncio
import aiohttp
import os
import json
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from backend.enhanced_database import SessionLocal, Media
from sentence_transformers import SentenceTransformer

# Load environment
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# Target Regional Languages: Telugu, Hindi, Tamil, Malayalam, Kannada
LANGUAGES = ['te', 'hi', 'ta', 'ml', 'kn']
PAGES_PER_LANGUAGE = 50  # 50 pages * 20 movies = 1000 top movies per language

async def fetch_movie_details(session, movie_id, semaphore):
    """Fetches full movie details AND JustWatch providers in a single API call."""
    async with semaphore:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&append_to_response=watch/providers"
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            return None

async def ingest_regional_movies():
    print("🚀 Starting High-Concurrency Regional Data Ingestion...")
    semaphore = asyncio.Semaphore(40) # Keep under TMDB 50 req/sec limit
    
    async with aiohttp.ClientSession() as session:
        for lang in LANGUAGES:
            print(f"--- Sweeping TMDB for Top '{lang.upper()}' Movies ---")
            movie_ids = set()
            
            # 1. Gather all top movie IDs for this language
            for page in range(1, PAGES_PER_LANGUAGE + 1):
                url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_original_language={lang}&sort_by=vote_count.desc&page={page}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for r in data.get('results', []):
                            movie_ids.add(r['id'])
            
            print(f"Found {len(movie_ids)} high-quality {lang.upper()} movies. Fetching deep details & JustWatch data...")
            
            # 2. Fetch full details and providers concurrently
            tasks = [fetch_movie_details(session, mid, semaphore) for mid in movie_ids]
            detailed_movies = await asyncio.gather(*tasks)
            
            # 3. Save to Database
            db: Session = SessionLocal()
            saved_count = 0
            for md in detailed_movies:
                if not md or not md.get('overview'):
                    continue
                
                # Check if movie already exists to prevent duplicates
                exists = db.query(Media).filter(Media.tmdb_id == md['id']).first()
                if exists:
                    continue
                
                # Extract JustWatch Providers (specifically for India 'IN')
                providers = []
                if 'watch/providers' in md and 'results' in md['watch/providers']:
                    in_data = md['watch/providers']['results'].get('IN', {})
                    flatrate = in_data.get('flatrate', [])
                    providers = [p['provider_name'] for p in flatrate]

                new_media = Media(
                    tmdb_id=md['id'],
                    title=md['title'],
                    overview=md['overview'],
                    release_date=md.get('release_date', ''),
                    rating=md.get('vote_average', 0.0),
                    genres=[g['name'] for g in md.get('genres', [])],
                    keywords=providers, # Reusing keywords column to store platforms like 'Netflix', 'Amazon Prime'
                    media_type="movie",
                    original_language=lang
                )
                db.add(new_media)
                saved_count += 1
                
            db.commit()
            db.close()
            print(f"✅ Successfully inserted {saved_count} new {lang.upper()} movies into the database.\n")

if __name__ == "__main__":
    if not TMDB_API_KEY:
        print("ERROR: TMDB_API_KEY missing from .env")
    else:
        asyncio.run(ingest_regional_movies())
