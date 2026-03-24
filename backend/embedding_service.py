"""
MIRAI — Embedding Service
=========================
Singleton wrapper around the SentenceTransformer model.
Loaded once at application startup; reused across all requests.

Model: paraphrase-multilingual-MiniLM-L12-v2 (384 dimensions)
Supports 50+ languages out of the box — no translation step required.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384


class EmbeddingService:
    """
    Thread-safe singleton that wraps SentenceTransformer.

    Usage::

        service = get_embedding_service()
        vector = service.embed("A mind-bending sci-fi thriller")
        vectors = service.embed_batch(["query1", "query2"])
    """

    def __init__(self) -> None:
        logger.info("Loading SentenceTransformer model: %s …", MODEL_NAME)
        self._model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded (dim=%d).", EMBEDDING_DIM)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(self, text: str) -> List[float]:
        """
        Embed a single string and return a L2-normalised 384-dim vector.

        Normalisation ensures cosine similarity == dot product, which is
        required for the pgvector ``<=>`` operator to return correct scores.
        """
        if not text or not text.strip():
            return [0.0] * EMBEDDING_DIM

        try:
            vector: np.ndarray = self._model.encode(
                text,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            return vector.tolist()
        except Exception as exc:
            logger.error("Embedding failed for text '%s…': %s", text[:80], exc)
            return [0.0] * EMBEDDING_DIM

    def embed_batch(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        """
        Embed a list of strings in one efficient batch call.
        Returns a parallel list of 384-dim normalised vectors.
        """
        if not texts:
            return []

        try:
            vectors: np.ndarray = self._model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            return [v.tolist() for v in vectors]
        except Exception as exc:
            logger.error("Batch embedding failed: %s", exc)
            return [[0.0] * EMBEDDING_DIM for _ in texts]


# ---------------------------------------------------------------------------
# Module-level singleton — loaded once, shared everywhere
# ---------------------------------------------------------------------------

_service: EmbeddingService | None = None


def load_embedding_service() -> EmbeddingService:
    """Call this once during FastAPI lifespan startup."""
    global _service
    _service = EmbeddingService()
    return _service


def get_embedding_service() -> EmbeddingService:
    """
    Return the already-loaded singleton.
    Raises ``RuntimeError`` if ``load_embedding_service()`` was not called first.
    """
    if _service is None:
        raise RuntimeError(
            "EmbeddingService is not initialised. "
            "Call load_embedding_service() during application startup."
        )
    return _service
