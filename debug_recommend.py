"""
debug_recommend.py — Simulate the recommend call to find the real error
"""
import sys, os, traceback
sys.path.insert(0, r'c:\Users\rohan\Downloads\movie-rec-project\backend')
os.chdir(r'c:\Users\rohan\Downloads\movie-rec-project\backend')

# Set env
os.environ['DATABASE_URL'] = 'sqlite:///C:/Users/rohan/Downloads/movie-rec-project/mirai.db'
os.environ['PYTHONIOENCODING'] = 'utf-8'

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    from enhanced_database import get_db_session, Media, RecommendationCache, EnhancedInteraction, SearchAnalytics
    from sqlalchemy import or_
    import numpy as np

    print("Step 1: Loading DB...")
    db = get_db_session()
    count = db.query(Media).count()
    print(f"  Media count: {count}")

    print("Step 2: Loading FAISS...")
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        model_kwargs={"device": "cpu"},
    )
    print("  Embeddings loaded")
    
    faiss_path = r'c:\Users\rohan\Downloads\movie-rec-project\data\faiss_index'
    vector_store = FAISS.load_local(faiss_path, embeddings, allow_dangerous_deserialization=True)
    print("  FAISS loaded")

    print("Step 3: Embedding query...")
    query = "action movie"
    query_embedding = np.array(embeddings.embed_query(query), dtype=np.float32)
    print(f"  Embedding shape: {query_embedding.shape}")

    print("Step 4: FAISS similarity search...")
    docs_with_scores = vector_store.similarity_search_with_score(query, k=10)
    print(f"  Got {len(docs_with_scores)} docs")
    if docs_with_scores:
        doc, score = docs_with_scores[0]
        print(f"  Sample doc meta: {doc.metadata}")
        print(f"  Sample score: {score}")

    print("Step 5: DB lookup for docs...")
    candidates = []
    for doc, sim_score in docs_with_scores:
        tmdb_id = doc.metadata.get("tmdb_id") or doc.metadata.get("id")
        if not tmdb_id:
            print(f"  No tmdb_id in meta: {doc.metadata.keys()}")
            continue
        media_record = db.query(Media).filter(Media.tmdb_id == int(tmdb_id)).first()
        if media_record:
            platforms = [p.name for p in media_record.platforms]
            c = {
                "id": int(media_record.tmdb_id),
                "db_id": int(media_record.db_id),
                "title": media_record.title,
                "overview": media_record.overview or "",
                "release_date": media_record.release_date or "",
                "rating": float(media_record.rating or 0),
                "poster_path": media_record.poster_path or "",
                "media_type": media_record.media_type,
                "genres": media_record.genres or [],
                "keywords": media_record.keywords or [],
                "popularity": float(media_record.popularity_score or 0),
                "original_language": media_record.original_language or "en",
                "runtime": media_record.runtime,
                "director": media_record.director,
                "cast": media_record.cast or [],
                "similarity_score": float(sim_score),
                "streaming_platforms": platforms,
            }
            candidates.append(c)
    print(f"  Got {len(candidates)} candidates")
    
    print("Step 6: Rec engine scoring...")
    from advanced_recommendation_engine import AdvancedRecommendationEngine
    rec_engine = AdvancedRecommendationEngine(embeddings_model=embeddings)
    top_candidates = candidates[:10]
    ranked = rec_engine.hybrid_content_collaborative_scoring(
        query_embedding=query_embedding,
        user_id="test_user",
        candidate_items=top_candidates,
        user_interactions=[],
        item_features={},
    )
    print(f"  Ranked {len(ranked)} items")
    if ranked:
        print(f"  Top item: {ranked[0].get('title')}")

    db.close()
    print("\nSUCCESS - All steps passed!")
    
except Exception as e:
    print(f"\nERROR at above step: {e}")
    traceback.print_exc()
