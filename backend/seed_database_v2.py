import requests
import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.enhanced_database import Base, Media, init_enhanced_db
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
DATABASE_URL = "sqlite:///./mirai.db"

# Setup DB connection
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

def get_embeddings_model():
    print("Loading embedding model...")
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

def fetch_tmdb(endpoint, params={}):
    url = f"https://api.themoviedb.org/3{endpoint}"
    params['api_key'] = TMDB_API_KEY
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        print(f"Error fetching {endpoint}: {response.status_code}")
    except Exception as e:
        print(f"Request failed: {e}")
    return None

def seed_database():
    print("Starting database seeding...")
    
    # 1. RESET DATABASE
    print("Resetting database schema...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("Dropped all tables.")
    except Exception as e:
        print(f"Error dropping tables: {e}")
        
    print("Creating new tables...")
    try:
        init_enhanced_db() # Uses Base.metadata.create_all inside
        print("Tables created successfully.")
    except Exception as e:
        print(f"Warning during init: {e}")
        Base.metadata.create_all(bind=engine)
    
    # Load model
    embeddings_model = get_embeddings_model()
    
    # Fetch Trending Movies
    print("Fetching trending movies...")
    movies_data = fetch_tmdb("/trending/movie/week")
    
    # Fetch Trending TV
    print("Fetching trending TV shows...")
    tv_data = fetch_tmdb("/trending/tv/week")
    
    items_added = 0
    all_items = []
    
    if movies_data and 'results' in movies_data:
        all_items.extend([(x, 'movie') for x in movies_data['results']])
        
    if tv_data and 'results' in tv_data:
        all_items.extend([(x, 'tv') for x in tv_data['results']])
        
    print(f"Found {len(all_items)} items to process.")
    
    texts_for_faiss = []
    metadatas_for_faiss = []
    
    for item, media_type in all_items:
        try:
            tmdb_id = item['id']
            title = item.get('title') if media_type == 'movie' else item.get('name')
            overview = item.get('overview', '')
            release_date = item.get('release_date') if media_type == 'movie' else item.get('first_air_date')
            
            # Skip if no overview or title
            if not title or not overview:
                continue
            
            # Create text for embedding
            full_text = f"{title}. {overview} Released: {release_date} Type: {media_type}"
            
            # Add to FAISS lists
            texts_for_faiss.append(full_text)
            metadatas_for_faiss.append({
                "tmdb_id": tmdb_id,
                "title": title,
                "media_type": media_type,
                "release_date": release_date
            })
            
            media = Media(
                tmdb_id=tmdb_id,
                title=title,
                overview=overview,
                release_date=release_date,
                rating=item.get('vote_average'),
                poster_path=f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get('poster_path') else None,
                media_type=media_type,
                original_language=item.get('original_language'),
                popularity_score=item.get('popularity'),
                trending_score=item.get('vote_count'), 
                # embedding removed as it's not in schema
                genres=json.dumps(item.get('genre_ids', []))
            )
            
            session.add(media)
            items_added += 1
            
            if items_added % 10 == 0:
                print(f"Processed {items_added} items...")
            
        except Exception as e:
            print(f"Error adding {media_type} {item.get('id')}: {e}")
            continue

    session.commit()
    print(f"Successfully seeded {items_added} new items to SQL database!")
    
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
    seed_database()
