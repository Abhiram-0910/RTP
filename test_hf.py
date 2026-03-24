import sys
from langchain_huggingface import HuggingFaceEmbeddings

print("Initializing embeddings...")
try:
    embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-MiniLM-L12-v2")
    print("Embeddings loaded successfully.")
    
    print("Testing embed_query...")
    vec = embeddings.embed_query("hello world")
    print(f"Success! Vector len: {len(vec)}")
except Exception as e:
    print(f"Python Exception caught: {e}")

sys.exit(0)
