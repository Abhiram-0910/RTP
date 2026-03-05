import pandas as pd
import os
from database import SessionLocal, Media, engine, Base
import sys
import io

# Force UTF-8 for prints to avoid 'charmap' errors on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure tables exist
Base.metadata.create_all(bind=engine)

def migrate():
    print("Initializing database tables...")
    db = SessionLocal()
    
    print("Migrating movies...")
    if os.path.exists("../data/movies_metadata.csv"):
        movies_df = pd.read_csv("../data/movies_metadata.csv")
        movies_added = 0
        for _, row in movies_df.iterrows():
            # Check if exists
            exists = db.query(Media).filter(Media.tmdb_id == int(row['id']), Media.media_type == 'movie').first()
            if not exists:
                movie = Media(
                    tmdb_id=int(row['id']),
                    title=str(row['title']),
                    overview=str(row.get('overview', '')),
                    release_date=str(row.get('release_date', '')),
                    rating=float(row.get('vote_average', 0.0)),
                    poster_path=str(row.get('poster_path', '')),
                    media_type='movie'
                )
                db.add(movie)
                movies_added += 1
        db.commit()
        print(f"Migrated {movies_added} movies to database.")
    else:
        print("../data/movies_metadata.csv not found.")
    
    print("Migrating TV Shows...")
    if os.path.exists("../data/tmdb_tv_shows.csv"):
        tv_df = pd.read_csv("../data/tmdb_tv_shows.csv")
        tv_added = 0
        for _, row in tv_df.iterrows():
            exists = db.query(Media).filter(Media.tmdb_id == int(row['id']), Media.media_type == 'tv').first()
            if not exists:
                tv = Media(
                    tmdb_id=int(row['id']),
                    title=str(row['title']),
                    overview=str(row.get('overview', '')),
                    release_date=str(row.get('release_date', '')),
                    rating=float(row.get('rating', 0.0)),
                    poster_path=str(row.get('poster_path', '')),
                    media_type='tv'
                )
                db.add(tv)
                tv_added += 1
        db.commit()
        print(f"Migrated {tv_added} TV shows to database.")
    else:
        print("../data/tmdb_tv_shows.csv not found. Run fetch_tv_shows.py first to get them.")
        
    db.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
