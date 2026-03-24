import json
import logging
import numpy as np
from typing import List, Optional, Tuple

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError
from sentence_transformers import SentenceTransformer

from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

from .models import Media
from .faiss_fallback import FAISSFallback

logger = logging.getLogger(__name__)

# Singleton FAISS index representing in-memory fallback
faiss_fallback_index = FAISSFallback()

async def populate_faiss_fallback(db: AsyncSession):
    """
    Called on engine startup to front-load the fallback FAISS index dynamically.
    """
    logger.info("Initializing FAISS fallback cache...")
    stmt = select(Media.id, Media.embedding).where(Media.embedding.is_not(None))
    result = await db.execute(stmt)
    rows = result.all()
    
    if not rows:
        logger.info("No media stored yet, skipping FAISS initialization.")
        return

    ids = []
    embeddings = []
    for row in rows:
        ids.append(row.id)
        emb = row.embedding
        if isinstance(emb, str):
            try:
                emb = json.loads(emb)
            except Exception:
                continue
        embeddings.append(emb)
        
    vectors = np.array(embeddings, dtype=np.float32)
    faiss_fallback_index.add_embeddings(vectors, ids)
    logger.info("FAISS fallback populated sequentially with %d vectors", len(ids))


class HybridRecommendationEngine:
    """
    Core AI brain of MIRAI.
    Combines pgvector ANN search with cross-lingual embeddings, hybrid scoring,
    category post-filtering, and MMR (Maximal Marginal Relevance) diversification.
    """

    def __init__(self, db_session: AsyncSession):
        # Load the precise paraphrase-multilingual-MiniLM-L12-v2 model via SentenceTransformer
        logger.info("Initializing HybridRecommendationEngine and loading SentenceTransformer...")
        self.model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        self.db = db_session
        
        # Initialize langdetect deterministic behavior
        from langdetect import DetectorFactory
        DetectorFactory.seed = 0

    def detect_language(self, query: str) -> str:
        """
        Detects the ISO 639-1 language code of the query string.
        Falls back to 'en' if the input is too short, ambiguous, or empty.
        """
        if not query or not query.strip():
            return "en"
        try:
            return detect(query)
        except LangDetectException:
            return "en"

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embeds a text query using the loaded SentenceTransformer model.
        Returns a normalized 384-dimensional dense L2 vector as float32.
        """
        # normalize_embeddings=True ensures dot product == cosine similarity
        vector = self.model.encode(query, normalize_embeddings=True, show_progress_bar=False)
        return np.array(vector, dtype=np.float32)

    async def vector_search(self, query_embedding: np.ndarray, top_k: int = 20) -> List[Tuple[Media, float]]:
        """
        Performs an exact or approximate nearest neighbor vector search against PostgreSQL.
        Gracefully degrades to the local FAISS index if the pgvector operator `<=>` errors or is entirely absent.
        """
        # Convert the float32 numpy array into a pgvector-compatible string literal payload
        vec_literal = "[" + ",".join(f"{v:.6f}" for v in query_embedding.tolist()) + "]"

        # The pgvector '<=>' operator computes cosine distance (1 - cosine similarity)
        # We project 1 - (distance) back into pure similarity
        sql = text("""
            SELECT *, 1 - (embedding <=> :vec::vector) AS similarity 
            FROM media 
            ORDER BY embedding <=> :vec::vector 
            LIMIT :k
        """)

        try:
            result = await self.db.execute(sql, {"vec": vec_literal, "k": top_k})
            rows = result.mappings().all()

            candidates: List[Tuple[Media, float]] = []
            for row in rows:
                # We explicitly extract similarity and pop it out to instantiate the ORM model cleanly
                row_dict = dict(row)
                similarity = float(row_dict.pop("similarity", 0.0))
                
                # The pgvector raw value may come back as a string from asyncpg depending on dialect mapping
                if "embedding" in row_dict and isinstance(row_dict["embedding"], str):
                    try:
                        row_dict["embedding"] = json.loads(row_dict["embedding"])
                    except Exception:
                        pass
                    
                candidates.append((Media(**row_dict), similarity))

            return candidates
            
        except (OperationalError, ProgrammingError, DBAPIError) as e:
            # Revert the poisoned transaction state sequentially so subsequent routing isn't blocked
            await self.db.rollback()
            logger.warning("pgvector SQL execution failed natively (%s). Degrading logic to FAISS fallback...", e.__class__.__name__)
            
            # Immediately default logic to FAISS
            if not faiss_fallback_index.is_ready():
                return []
                
            faiss_results = faiss_fallback_index.search(query_embedding, top_k)
            if not faiss_results:
                return []
                
            # Execute lookup reconstructing media identities via simple PK selection criteria
            matched_ids = [r[0] for r in faiss_results]
            stmt = select(Media).where(Media.id.in_(matched_ids))
            db_res = await self.db.execute(stmt)
            media_items = {m.id: m for m in db_res.scalars().all()}
            
            # Reconstruct sequence identical to FAISS retrieval rankings
            degraded_candidates = []
            for m_id, sim in faiss_results:
                if m_id in media_items:
                    degraded_candidates.append((media_items[m_id], sim))
                    
            return degraded_candidates

    def hybrid_score(self, similarity: float, popularity_normalized: float, rating_normalized: float) -> float:
        """
        Calculates a final unified relevance score weighting semantic similarity,
        global popularity, and critical rating.
        """
        return (0.65 * similarity) + (0.25 * popularity_normalized) + (0.10 * rating_normalized)

    def mmr_rerank(self, candidates: List[Tuple[Media, float]], lambda_val: float = 0.5, top_n: int = 8) -> List[Tuple[Media, float]]:
        """
        Yields the most diverse, high-relevance set of recommendations using MMR.
        Maximizes: λ * relevance - (1-λ) * max_similarity_to_already_selected
        """
        if not candidates:
            return []

        selected: List[Tuple[Media, float]] = []
        unselected = list(candidates)

        # Helper method for computing standard cosine similarity between two feature arrays
        def _cosine_similarity(vec1, vec2) -> float:
            if vec1 is None or vec2 is None:
                return 0.0
            v1, v2 = np.array(vec1, dtype=np.float32), np.array(vec2, dtype=np.float32)
            norm = np.linalg.norm(v1) * np.linalg.norm(v2)
            if norm == 0:
                return 0.0
            return float(np.dot(v1, v2) / norm)

        while len(selected) < top_n and unselected:
            best_idx = -1
            best_mmr_score = -float('inf')

            for idx, candidate in enumerate(unselected):
                media, relevance_score = candidate

                # If we haven't selected anything yet, diversity penalty is 0
                if not selected:
                    max_sim_to_selected = 0.0
                else:
                    # Look at every item we've already selected and find the highest similarity 
                    # between the pending candidate and the selected pool
                    max_sim_to_selected = max(
                        _cosine_similarity(media.embedding, s_media.embedding) 
                        for s_media, _ in selected
                    )

                # The core MMR formula
                mmr_score = (lambda_val * relevance_score) - ((1.0 - lambda_val) * max_sim_to_selected)

                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_idx = idx

            # Add the best candidate directly into the selected pool and pop it from unselected
            if best_idx >= 0:
                selected.append(unselected.pop(best_idx))
            else:
                break

        return selected

    async def recommend(self, query: str, platform_filter: Optional[str] = None, genre_filter: Optional[str] = None) -> Tuple[List[Tuple[Media, float]], str]:
        """
        Full orchestration pipeline for generating context-aware recommendations.
        Returns a tuple containing the ranked media instances and the detected query language.
        """
        # Step 1: Detect Language
        detected_language = self.detect_language(query)

        # Step 2: Embed Query
        query_embedding = self.embed_query(query)

        # Step 3: Vector Search 
        # Increase the search neighborhood dynamically to account for strict post-filtering
        k_neighborhood = 100 if (platform_filter or genre_filter) else 20
        raw_candidates = await self.vector_search(query_embedding, top_k=k_neighborhood)

        # Step 4: Apply platform & genre post-filters
        filtered_candidates: List[Tuple[Media, float]] = []
        for media, similarity in raw_candidates:
            # Check genres: if filter is strictly explicitly requested, media must contain it
            if genre_filter:
                if not media.genres or genre_filter.lower() not in (g.lower() for g in media.genres):
                    continue

            # Check platforms: check if requested streaming venue exists anywhere in the JSONB dictionary
            if platform_filter:
                if not media.platforms:
                    continue
                # Evaluate whether the target platform exists in any territory
                has_platform = any(
                    platform_filter.lower() in (p.lower() for p in platform_list)
                    for territory, platform_list in media.platforms.items()
                )
                if not has_platform:
                    continue

            filtered_candidates.append((media, similarity))

            # Stop once we have 20 strong filtered candidates mathematically similar to initial k=20
            if len(filtered_candidates) == 20:
                break

        # Step 5: Assign Hybrid Score logic utilizing normalized auxiliary metrics
        scored_candidates: List[Tuple[Media, float]] = []
        for media, similarity in filtered_candidates:
            # Robust normalization. Popularity bounds heavily depending on TMDB API.
            rating_normalized = min(max((media.vote_average or 0.0) / 10.0, 0.0), 1.0)
            
            # The popularity score from ingestion may be previously scaled; we cap bounds.
            popularity_normalized = min(max(media.popularity or 0.0, 0.0), 1.0)

            final_hybrid_score = self.hybrid_score(
                similarity=similarity,
                popularity_normalized=popularity_normalized,
                rating_normalized=rating_normalized
            )
            scored_candidates.append((media, final_hybrid_score))

        # Sort the final scored candidate pool purely by relevance prior to MMR diversification
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # Step 6: MMR Restructuring
        top_n_diverse_results = self.mmr_rerank(
            candidates=scored_candidates,
            lambda_val=0.5,
            top_n=8
        )

        return top_n_diverse_results, detected_language
