import os
from dotenv import load_dotenv
from backend.enhanced_database import SessionLocal, Media
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# 1. Load environment variables from the root .env
# Since this script lives in 'backend/', go up one level
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

def run_nuclear_rebuild():
    print("🚀 Starting Nuclear FAISS Rebuild...")
    db = SessionLocal()
    
    try:
        all_media = db.query(Media).all()
        print(f"📦 Found {len(all_media)} total media items in PostgreSQL.")
        
        docs = []
        for m in all_media:
            # 1. Build the semantic text
            # Ensure we handle nulls for overview/genres
            genres_str = ", ".join(m.genres) if m.genres else ""
            overview_str = m.overview or ""
            content = f"Title: {m.title}. Genres: {genres_str}. Overview: {overview_str}"
            
            # 2. FORCE the exact metadata keys for strict filtering
            meta = {
                "original_language": m.original_language.lower() if m.original_language else "en",
                "media_type": m.media_type.lower() if m.media_type else "movie",
                "tmdb_id": m.tmdb_id
            }
            
            docs.append(Document(page_content=content, metadata=meta))
            
        print("🧠 Booting up Multilingual Embedding Model...")
        # Using the exact same model configured in the rag_engine for search consistency
        embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-MiniLM-L12-v2")
        
        print(f"⚡ Generating vectors for {len(docs)} documents. Please wait 1-3 minutes...")
        # Note: 19k embeddings will take consistent CPU time
        vector_db = FAISS.from_documents(docs, embeddings)
        
        # 3. Save to the global data directory
        # This matches the path expected by rag_chain.py: data/faiss_index
        save_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "faiss_index")
        os.makedirs(save_path, exist_ok=True)
        vector_db.save_local(save_path)
        
        print(f"✅ SUCCESS! Bulletproof index saved to {save_path}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_nuclear_rebuild()
