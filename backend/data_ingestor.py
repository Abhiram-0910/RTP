import os
import pandas as pd
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import sys
import io

# Force UTF-8 for prints to avoid 'charmap' errors on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure we can import from the root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)
from backend.enhanced_database import SessionLocal, Media

DATA_DIR = os.path.join(BASE_DIR, 'data')
FAISS_PATH = os.path.join(DATA_DIR, 'faiss_index')

class DataIngestor:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.vector_store = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ".", " ", ""]
        )

    def create_faiss_index(self):
        print("Loading data from database...")
        documents = []
        db = SessionLocal()
        try:
            # Query all media records from the database
            media_records = db.query(Media).all()
            print(f"Adding {len(media_records)} records from database...")

            for item in media_records:
                # Build rich text for semantic embedding
                parts = [f"Title: {item.title}"]
                if item.genres:
                    parts.append("Genres: " + ", ".join(item.genres))
                if item.keywords:
                    parts.append("Themes: " + ", ".join(item.keywords[:15]))
                if item.cast:
                    parts.append("Cast: " + ", ".join(item.cast))
                if item.director:
                    parts.append(f"Director: {item.director}")
                if item.release_date:
                    parts.append(f"Year: {item.release_date[:4]}")
                parts.append(f"Overview: {item.overview}")
                
                content = ". ".join(p for p in parts if p)
                
                # Split content into manageable chunks
                chunks = self.text_splitter.split_text(content)
                for i, chunk in enumerate(chunks):
                    documents.append(
                        Document(
                            page_content=chunk,
                            metadata={
                                "tmdb_id": int(item.tmdb_id),
                                "id": int(item.tmdb_id),  # Legacy support
                                "media_type": item.media_type,
                                "chunk_index": i,
                                "title": item.title
                            }
                        )
                    )
            
            if not documents and os.path.exists(os.path.join(DATA_DIR, "tmdb_5000_movies.csv")):
                print("Database empty. Falling back to CSV...")
                # ... existing CSV logic ...
                pass
        finally:
            db.close()

        if not documents:
            print("No documents to index. Build failed.")
            return

        print("Building new FAISS Vector Store... (this may take a few minutes)")
        self.vector_store = FAISS.from_documents(documents, self.embeddings)

        os.makedirs(FAISS_PATH, exist_ok=True)
        print(f"Saving FAISS index locally to {FAISS_PATH}...")
        self.vector_store.save_local(FAISS_PATH)

        # Generate movies_metadata.csv for DB migration script
        csv_path = os.path.join(DATA_DIR, "tmdb_5000_movies.csv")
        target_csv = os.path.join(DATA_DIR, "movies_metadata.csv")
        if os.path.exists(csv_path):
            movie_df = pd.read_csv(csv_path)
            movie_df.rename(columns={"vote_average": "rating"}, inplace=True)
            movie_df["poster_path"] = ""
            movie_df.to_csv(target_csv, index=False)

        print("🎉 FAISS index created successfully with unified metadata!")


if __name__ == "__main__":
    ingestor = DataIngestor()
    ingestor.create_faiss_index()
