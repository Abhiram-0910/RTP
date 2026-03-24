import sys
print("Testing FAISS import...")
try:
    import faiss
    print("FAISS imported.")
    
    from backend.rag_engine import populate_faiss_fallback_from_db
    print("Populating...")
    n = populate_faiss_fallback_from_db()
    print(f"Success! {n} vectors.")
except Exception as e:
    print(f"Exception: {e}")

sys.exit(0)
