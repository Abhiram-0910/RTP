import pandas as pd
import json
import os
import sys
import ast
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.enhanced_database import Base, Media, init_enhanced_db
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = "sqlite:///./mirai.db"
CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'tmdb_5000_movies.csv')

# Setup DB connection
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

def get_embeddings_model():
    print("Loading embedding model...")
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

def parse_json_safe(val):
    try:
        if pd.isna(val):
            return []
        return json.loads(val)
    except:
        try:
            return ast.literal_eval(val)
        except:
            return []

def seed_from_csv():
    print(f"Reading CSV from {CSV_PATH}...")
    try:
        df = pd.read_csv(CSV_PATH)
        print(f"Loaded {len(df)} movies from CSV.")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Sort by popularity to seed best content first
    df = df.sort_values('popularity', ascending=False).head(1000)
    print("Processing top 1000 movies...")

    # 1. RESET DATABASE
    print("Resetting database schema...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("Dropped all tables.")
    except Exception as e:
        print(f"Error dropping tables: {e}")
        
    try:
        init_enhanced_db()
    except Exception as e:
        print(f"Warning during init: {e}")
        Base.metadata.create_all(bind=engine)
    
    # Load model
    embeddings_model = get_embeddings_model()
    
    items_added = 0
    texts_for_faiss = []
    metadatas_for_faiss = []
    
    for _, row in df.iterrows():
        try:
            tmdb_id = int(row['id'])
            title = row['title']
            overview = str(row['overview']) if pd.notna(row['overview']) else ""
            release_date = str(row['release_date']) if pd.notna(row['release_date']) else ""
            
            if not title or not overview:
                continue
                
            # Parse genres
            genres_list = parse_json_safe(row['genres'])
            genre_names = [g['name'] for g in genres_list]
            
            # Create text for embedding
            full_text = f"{title}. {overview} Genres: {', '.join(genre_names)} Released: {release_date}"
            
            # Add to FAISS lists
            texts_for_faiss.append(full_text)
            metadatas_for_faiss.append({
                "tmdb_id": tmdb_id,
                "title": title,
                "media_type": "movie",
                "release_date": release_date
            })
            
            media = Media(
                tmdb_id=tmdb_id,
                title=title,
                overview=overview,
                release_date=release_date,
                rating=float(row['vote_average']) if pd.notna(row['vote_average']) else 0.0,
                poster_path=None, # CSV doesn't have poster path, handled by frontend fallback or fetch
                media_type='movie',
                original_language=str(row['original_language']),
                popularity_score=float(row['popularity']) if pd.notna(row['popularity']) else 0.0,
                trending_score=float(row['vote_count']) if pd.notna(row['vote_count']) else 0.0,
                # vote_count removed as it's not in schema
                genres=json.dumps(genre_names)
            )
            
            session.add(media)
            items_added += 1
            
            if items_added % 50 == 0:
                print(f"Processed {items_added} items...")
                
        except Exception as e:
            print(f"Error adding movie {row.get('title')}: {e}")
            continue

    session.commit()
    print(f"Successfully seeded {items_added} movies from CSV!")
    
    # Create FAISS index
    if texts_for_faiss:
        print("Creating FAISS index...")
        vector_store = FAISS.from_texts(
            texts=texts_for_faiss,
            embedding=embeddings_model,
            metadatas=metadatas_for_faiss
        )
        
        # Save FAISS index
        faiss_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'faiss_index')
        os.makedirs(os.path.dirname(faiss_path), exist_ok=True)
        vector_store.save_local(faiss_path)
        print(f"FAISS index saved to {faiss_path}")
    else:
        print("No items to index!")

if __name__ == "__main__":
    seed_from_csv()
