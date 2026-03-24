"""
Targeted script to seed the current Media table from tmdb_5000_movies.csv
without dropping tables or changing the schema.
"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from backend.database import SessionLocal, Media, Base, engine

def seed():
    # Ensure Media table exists
    Base.metadata.create_all(bind=engine)
    
    csv_path = "../data/tmdb_5000_movies.csv"
    if not os.path.exists(csv_path):
        print(f"Skipping seed: {csv_path} not found.")
        return
        
    df = pd.read_csv(csv_path)
    # Sort by popularity or just take the top 500 to keep it fast for testing
    if 'popularity' in df.columns:
        df = df.sort_values('popularity', ascending=False)
    
    df = df.head(1000)
    
    db = SessionLocal()
    added = 0
    try:
        # Get existing IDs to avoid duplicates
        existing_ids = {m[0] for m in db.query(Media.tmdb_id).all()}
        
        for _, row in df.iterrows():
            tmdb_id = int(row['id'])
            if tmdb_id in existing_ids:
                continue
                
            media = Media(
                tmdb_id=tmdb_id,
                title=str(row['title'])[:255],
                overview=str(row['overview']) if pd.notna(row['overview']) else "",
                release_date=str(row['release_date']) if pd.notna(row['release_date']) else "",
                rating=float(row['vote_average']) if pd.notna(row['vote_average']) else 0.0,
                poster_path=None,  # Not in CSV
                media_type="movie"
            )
            db.add(media)
            added += 1
            
            if added % 100 == 0:
                db.commit()
                print(f"Added {added} records...")
                
        db.commit()
        print(f"✅ Successfully seeded {added} new movie records.")
        print(f"Total movies in DB: {db.query(Media).count()}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
