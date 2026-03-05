import os
import pandas as pd
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document

import sys
import io

# Force UTF-8 for prints to avoid 'charmap' errors on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class DataIngestor:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.vector_store = None

    def create_faiss_index(self):
        print("Loading data...")
        documents = []

        # 1. Load Movies
        if os.path.exists("../data/tmdb_5000_movies.csv"):
            movie_df = pd.read_csv("../data/tmdb_5000_movies.csv")
            movie_df = movie_df[["id", "title", "overview", "release_date", "vote_average"]]
            movie_df = movie_df.dropna()
            
            for _, row in movie_df.iterrows():
                content = f"Title: {row['title']}. Overview: {row['overview']}"
                documents.append(
                    Document(
                        page_content=content,
                        metadata={"id": int(row["id"]), "media_type": "movie"}
                    )
                )
            print(f"Added {len(movie_df)} movies for indexing.")
        else:
            print("tmdb_5000_movies.csv not found.")

        # 2. Load TV Shows
        if os.path.exists("../data/tmdb_tv_shows.csv"):
            tv_df = pd.read_csv("../data/tmdb_tv_shows.csv")
            tv_df = tv_df.dropna(subset=["id", "title", "overview"])
            
            for _, row in tv_df.iterrows():
                content = f"Title: {row['title']}. Overview: {row['overview']}"
                documents.append(
                    Document(
                        page_content=content,
                        metadata={"id": int(row["id"]), "media_type": "tv"}
                    )
                )
            print(f"Added {len(tv_df)} TV shows for indexing.")
        else:
            print("tmdb_tv_shows.csv not found.")

        if not documents:
            print("No documents to index. Build failed.")
            return

        print("Building new FAISS Vector Store... (this may take a few minutes)")
        self.vector_store = FAISS.from_documents(documents, self.embeddings)

        os.makedirs("../data/faiss_index", exist_ok=True)
        print("Saving FAISS index locally...")
        self.vector_store.save_local("../data/faiss_index")

        # Generate movies_metadata.csv for DB migration script
        if os.path.exists("../data/tmdb_5000_movies.csv"):
            movie_df.rename(columns={"vote_average": "rating"}, inplace=True)
            movie_df["poster_path"] = ""
            movie_df.to_csv("../data/movies_metadata.csv", index=False)

        print("🎉 FAISS index created successfully with unified metadata!")


if __name__ == "__main__":
    ingestor = DataIngestor()
    ingestor.create_faiss_index()
