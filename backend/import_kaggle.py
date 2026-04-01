import pandas as pd
from backend.enhanced_database import SessionLocal, Media, init_enhanced_db
import ast

def import_kaggle_data():
    init_enhanced_db()
    print("Loading Kaggle dataset...")
    df = pd.read_csv("data/movies_metadata.csv", low_memory=False)
    
    # Clean data: must have title and overview
    df = df[df["overview"].notna() & df["title"].notna()]
    # df = df[df["imdb_id"].notna()] # Column not found in local CSV

    db = SessionLocal()
    added = 0
    print("Processing records...")
    
    for _, row in df.iterrows():
        try:
            tmdb_id = int(float(row.get("id", 0)))
            if tmdb_id <= 0: continue
            
            # Skip if we already fetched this from the live API
            exists = db.query(Media).filter(Media.tmdb_id == tmdb_id).first()
            if exists: continue
            
            genres_raw = ast.literal_eval(row.get("genres", "[]") or "[]")
            genres = [g["name"] for g in genres_raw if isinstance(g, dict)]
            
            db.add(Media(
                tmdb_id=tmdb_id,
                title=str(row["title"]),
                overview=str(row["overview"]),
                release_date=str(row.get("release_date", "")),
                rating=float(row.get("rating", 0) or 0),
                poster_path="",
                media_type="movie",
                original_language=str(row.get("original_language", "en")),
                popularity_score=float(row.get("popularity", 0) or 0),
                genres=genres,
            ))
            added += 1
            if added % 500 == 0:
                db.commit()
                print(f"Added {added} Kaggle movies...")
        except Exception:
            # Silently skip malformed rows
            continue
            
    db.commit()
    db.close()
    print(f"Done. Total Kaggle movies added: {added}")

if __name__ == "__main__":
    import_kaggle_data()