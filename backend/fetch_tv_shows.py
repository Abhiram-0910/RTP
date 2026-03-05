import os
import requests
import pandas as pd
from dotenv import load_dotenv
import time

load_dotenv()

import sys
import io

# Force UTF-8 for prints to avoid 'charmap' errors on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
if not TMDB_API_KEY:
    print("Warning: TMDB_API_KEY not found in .env file.")
    print("Please add it to fetch real TV shows. Using a tiny mock dataset for now to unblock the build.")
    TMDB_API_KEY = "mock"

def fetch_popular_tv_shows(target_count=5000):
    if TMDB_API_KEY == "mock":
        # Create a tiny mock CSV so the rest of the pipeline works
        os.makedirs("../data", exist_ok=True)
        shows = [{
            "id": 1399, "title": "Game of Thrones", "overview": "Nine noble families fight for control over the lands of Westeros.",
            "release_date": "2011-04-17", "rating": 8.4, "poster_path": "/1XS1oqL89opfnbLl8WnZY1O1uJx.jpg", "media_type": "tv"
        }, {
            "id": 66732, "title": "Stranger Things", "overview": "When a young boy vanishes, a small town uncovers a mystery involving secret experiments...",
            "release_date": "2016-07-15", "rating": 8.6, "poster_path": "/49WJfeN0moxb9IPfGn8IFqDziBG.jpg", "media_type": "tv"
        }]
        pd.DataFrame(shows).to_csv("../data/tmdb_tv_shows.csv", index=False)
        print("Saved mock TV shows to data/tmdb_tv_shows.csv!")
        return
        
    print(f"Fetching {target_count} TV shows from TMDB API...")
    shows = []
    
    # 20 results per page, so we need target_count / 20 pages
    total_pages = min((target_count // 20) + 1, 500) # TMDB limits to 500 pages for discover
    
    for page in range(1, total_pages + 1):
        url = f"https://api.themoviedb.org/3/discover/tv?api_key={TMDB_API_KEY}&language=en-US&sort_by=popularity.desc&page={page}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                results = response.json().get("results", [])
                for item in results:
                    shows.append({
                        "id": int(item["id"]),
                        "title": item.get("name", ""),
                        "overview": item.get("overview", ""),
                        "release_date": item.get("first_air_date", ""),
                        "rating": float(item.get("vote_average", 0.0)),
                        "poster_path": item.get("poster_path", ""),
                        "media_type": "tv"
                    })
                print(f"✅ Fetched page {page}/{total_pages} ({len(shows)} shows total)")
            else:
                print(f"❌ Error fetching page {page}: {response.status_code}")
                time.sleep(1) # Back off if error
        except Exception as e:
            print(f"❌ Exception on page {page}: {e}")
            
        if len(shows) >= target_count:
            break
            
    # Save to CSV
    os.makedirs("../data", exist_ok=True)
    df = pd.DataFrame(shows)
    df.to_csv("../data/tmdb_tv_shows.csv", index=False)
    print(f"🎉 Saved {len(shows)} TV shows to data/tmdb_tv_shows.csv!")
    return df

if __name__ == "__main__":
    fetch_popular_tv_shows(5000)
