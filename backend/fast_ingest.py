import asyncio
import aiohttp
import os
import time
from dotenv import load_dotenv
from backend.enhanced_database import SessionLocal, Media, init_enhanced_db

load_dotenv()
TMDB_KEY = os.getenv("TMDB_API_KEY")
SEMAPHORE = asyncio.Semaphore(40)  # 40 concurrent requests max

async def fetch(session, url, params):
    async with SEMAPHORE:
        try:
            async with session.get(url, params={**params, "api_key": TMDB_KEY}, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    return await r.json()
                if r.status == 429:
                    await asyncio.sleep(2)
        except Exception as e:
            print(f"Fetch error: {e}")
            pass
    return None

async def get_ids(session, media_type, pages=250):
    """Discover IDs across multiple pages concurrently."""
    ep = f"/discover/{media_type}"
    tasks = [
        fetch(session, f"https://api.themoviedb.org/3{ep}", 
              {"sort_by": "popularity.desc", "page": p, "vote_count.gte": 30})
        for p in range(1, pages + 1)
    ]
    results = await asyncio.gather(*tasks)
    ids = set()
    for r in results:
        if r:
            for item in r.get("results", []):
                ids.add(item["id"])
    return list(ids)

async def get_details(session, tmdb_id, media_type):
    ep = "movie" if media_type == "movie" else "tv"
    return await fetch(session, 
        f"https://api.themoviedb.org/3/{ep}/{tmdb_id}",
        {"append_to_response": "credits,keywords,watch/providers", "language": "en-US"})

async def ingest(target=10500):
    init_enhanced_db()
    db = SessionLocal()
    existing = {r[0] for r in db.query(Media.tmdb_id).all()}
    
    connector = aiohttp.TCPConnector(limit=60, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("Discovering IDs...")
        movie_ids = await get_ids(session, "movie", 300)
        tv_ids = await get_ids(session, "tv", 200)
        
        # Deduplicate all IDs across both search types
        id_map = {i: "movie" for i in movie_ids}
        for i in tv_ids:
            if i not in id_map:
                id_map[i] = "tv"
        
        all_ids = list(id_map.items())
        
        # Filter out existing IDs
        all_ids = [(i, t) for i, t in all_ids if i not in existing]
        print(f"Fetching details for {len(all_ids)} new titles...")
        
        tasks = [get_details(session, tid, mt) for tid, mt in all_ids[:target]]
        results = await asyncio.gather(*tasks)
        
        added = 0
        for (tmdb_id, media_type), raw in zip(all_ids[:target], results):
            if not raw: continue
            title = raw.get("title") or raw.get("name", "")
            overview = raw.get("overview", "")
            if not title or not overview or len(overview) < 20: continue
            
            db.add(Media(
                tmdb_id=tmdb_id,
                title=title,
                overview=overview,
                release_date=raw.get("release_date") or raw.get("first_air_date", ""),
                rating=float(raw.get("vote_average", 0)),
                poster_path=raw.get("poster_path", ""),
                media_type=media_type,
                original_language=raw.get("original_language", "en"),
                popularity_score=float(raw.get("popularity", 0)),
                genres=[g["name"] for g in raw.get("genres", [])],
                keywords=[k["name"] for k in raw.get("keywords", {}).get("keywords", [])[:20]],
                cast=[c["name"] for c in raw.get("credits", {}).get("cast", [])[:7]],
            ))
            added += 1
            if added % 200 == 0:
                db.commit()
                print(f"  Committed {added} records...")
        
        db.commit()
        print(f"Done. Added {added} titles in total.")
    db.close()

if __name__ == "__main__":
    asyncio.run(ingest())