import faiss
import numpy as np
from typing import List, Tuple

class FAISSFallback:
    """
    On-disk/In-memory vector index fallback used strictly when the primary
    PostgreSQL pgvector extension is absent computationally or errors.
    """
    def __init__(self):
        # The paraphrase-multilingual-MiniLM-L12-v2 model emits 384 dimensions
        self.index = faiss.IndexFlatIP(384)
        self.id_map: List[int] = []

    def add_embeddings(self, embeddings: np.ndarray, ids: List[int]) -> None:
        """
        Populate the FAISS index normalized natively via inner product calculating cosine similarity.
        """
        if len(embeddings) == 0:
            return
            
        embeddings_copy = embeddings.copy()
        # L2 normalization ensures Inner Product computation == Cosine Similarity
        faiss.normalize_L2(embeddings_copy)
        self.index.add(embeddings_copy)
        self.id_map.extend(ids)

    def search(self, query_embedding: np.ndarray, top_k: int) -> List[Tuple[int, float]]:
        """
        Executes highly efficient cosine similarity lookup natively without database joins.
        """
        if not self.is_ready():
            return []
            
        # Guarantee correct dimensionality boundaries
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
            
        query_copy = query_embedding.copy()
        faiss.normalize_L2(query_copy)
        
        # Output resolves raw scores and numerical index mapping
        scores, indices = self.index.search(query_copy, top_k)
        
        results: List[Tuple[int, float]] = []
        for j, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.id_map):
                results.append((self.id_map[idx], float(scores[0][j])))
                
        return results

    def is_ready(self) -> bool:
        return self.index.ntotal > 0
