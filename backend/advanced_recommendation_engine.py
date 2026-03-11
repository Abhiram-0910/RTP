import hashlib
import logging
import warnings
from functools import lru_cache

import numpy as np
import scipy.sparse as sp
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ── ALS backend availability check ──────────────────────────────────────────────────────
# implicit is optional — if absent, MF score gracefully falls back to 0.5.
try:
    from implicit.als import AlternatingLeastSquares as _ALS
    _ALS_AVAILABLE = True
    logger.info("[MF] implicit library found — ALS matrix factorization enabled.")
except ImportError:
    _ALS_AVAILABLE = False
    logger.warning(
        "[MF] implicit not installed — matrix factorization will return 0.5 (neutral). "
        "Install with: pip install implicit"
    )

# ── Sentiment backend selection ──────────────────────────────────────────────────────
# We try VADER first (fast, dependency-free install: `pip install vaderSentiment`).
# If it is not available we fall back to a HuggingFace zero-shot pipeline which
# downloads on first use but requires no extra GPU.
_VADER_ANALYZER = None
_HF_SENTIMENT_PIPE = None

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer as _VaderAnalyzer
    _VADER_ANALYZER = _VaderAnalyzer()
    logger.info("[Sentiment] Using VADER for review polarity analysis.")
except ImportError:
    logger.warning(
        "[Sentiment] vaderSentiment not installed — will attempt HuggingFace pipeline. "
        "Install with: pip install vaderSentiment"
    )


class AdvancedRecommendationEngine:
    def __init__(self, embeddings_model=None):
        """
        embeddings_model: an instance of HuggingFaceEmbeddings (or compatible).
        Pass it in so we can compute real item embeddings instead of random vectors.
        """
        self.embeddings_model = embeddings_model

        self.content_weights = {
            'genre': 0.25,
            'overview': 0.35,
            'keywords': 0.20,
            'cast': 0.10,
            'director': 0.10
        }

        self.collaborative_weights = {
            'user_similarity': 0.4,
            'item_similarity': 0.3,
            'rating_prediction': 0.3
        }

        self.diversity_params = {
            'lambda': 0.7,          # Relevance vs. diversity trade-off
            'max_similarity': 0.8,  # Maximum allowed similarity between results
            'genre_diversity_weight': 0.3
        }

        self.trending_weights = {
            'recency': 0.4,
            'popularity': 0.3,
            'user_engagement': 0.3
        }

    # ── Public API ─────────────────────────────────────────────────────────────

    def hybrid_content_collaborative_scoring(
        self,
        query_embedding: np.ndarray,
        user_id: str,
        candidate_items: List[Dict],
        user_interactions: List[Dict],
        item_features: Dict,
    ) -> List[Dict]:
        """
        Advanced hybrid scoring combining:
          - Content-based cosine similarity (real query embedding vs. item embedding)
          - Collaborative filtering (user history)
          - Trending/popularity signals
        """
        content_scores = self._calculate_content_scores(query_embedding, candidate_items)
        collab_scores = self._calculate_collaborative_scores(
            user_id, candidate_items, user_interactions, item_features
        )
        trending_scores = self._calculate_trending_scores(candidate_items)

        final_scores = []
        for i, item in enumerate(candidate_items):
            content_score = content_scores[i] if i < len(content_scores) else 0.5
            collab_score = collab_scores[i] if i < len(collab_scores) else 0.5
            trending_score = trending_scores[i] if i < len(trending_scores) else 0.5

            # Dynamic weight adjustment based on history depth
            if len(user_interactions) > 10:
                final_score = 0.40 * content_score + 0.40 * collab_score + 0.20 * trending_score
            else:
                final_score = 0.70 * content_score + 0.20 * collab_score + 0.10 * trending_score

            final_scores.append({
                **item,
                'content_score': round(content_score, 4),
                'collaborative_score': round(collab_score, 4),
                'trending_score': round(trending_score, 4),
                'final_score': round(final_score, 4),
            })

        return sorted(final_scores, key=lambda x: x['final_score'], reverse=True)

    def apply_diversity_filtering(
        self, ranked_items: List[Dict], max_results: int = 10
    ) -> List[Dict]:
        """Apply MMR-based diversity filtering."""
        if len(ranked_items) <= max_results:
            return ranked_items[:max_results]

        diverse_results = [ranked_items[0]]
        selected_genres = set(ranked_items[0].get("genres", []))
        selected_years = {self._extract_year(ranked_items[0].get("release_date", ""))}

        for item in ranked_items[1:]:
            if len(diverse_results) >= max_results:
                break

            diversity_score = self._calculate_diversity_score(item, diverse_results)
            item_genres = set(item.get("genres", []))
            genre_overlap = len(item_genres.intersection(selected_genres))
            genre_diversity = 1 - (genre_overlap / max(len(item_genres), 1))

            item_year = self._extract_year(item.get("release_date", ""))
            year_diversity = 1 if item_year not in selected_years else 0.5

            combined_diversity = (
                diversity_score * 0.6
                + genre_diversity * 0.3
                + year_diversity * 0.1
            )

            mmr_score = (
                self.diversity_params['lambda'] * item.get('final_score', 0.5)
                + (1 - self.diversity_params['lambda']) * combined_diversity
            )

            if combined_diversity > 0.3 or item.get('final_score', 0) > 0.8:
                diverse_results.append(item)
                selected_genres.update(item_genres)
                if item_year:
                    selected_years.add(item_year)

        return diverse_results

    def generate_serendipitous_recommendations(
        self,
        user_interactions: List[Dict],
        all_items: List[Dict],
        num_serendipitous: int = 2,
    ) -> List[Dict]:
        """Generate serendipitous (pleasant-surprise) recommendations."""
        if not user_interactions:
            return []

        user_preferences = self._extract_user_preferences(user_interactions)
        serendipitous_candidates = []

        for item in all_items:
            if any(inter.get("tmdb_id") == item.get("id") for inter in user_interactions):
                continue

            serendipity_score = self._calculate_serendipity_score(item, user_preferences)
            if serendipity_score > 0.6:
                serendipitous_candidates.append({
                    **item,
                    "serendipity_score": serendipity_score,
                    "reason": self._generate_serendipity_reason(item, user_preferences),
                })

        serendipitous_candidates.sort(key=lambda x: x["serendipity_score"], reverse=True)
        return serendipitous_candidates[:num_serendipitous]

    # ── Private Helpers ────────────────────────────────────────────────────────

    def _calculate_sentiment_score(self, reviews_text: str) -> float:
        """
        Parse *reviews_text* and return a **normalised polarity score** in [-1.0, 1.0].

        Positive scores  (+0.1 → +1.0) indicate overwhelmingly favourable reviews.
        Negative scores  (-0.1 → -1.0) indicate predominantly critical/negative reviews.
        Values near zero indicate mixed or neutral sentiment.

        Backend priority
        ----------------
        1. **VADER** (``vaderSentiment``) — fast, rule-based, great for short review
           snippets. Returns the ``compound`` score which is already in [-1, 1].
        2. **HuggingFace pipeline** (``distilbert-base-uncased-finetuned-sst-2-english``
           loaded lazily) — slightly slower but more accurate on full sentences.
        3. Neutral fallback (0.0) when no backend is available.
        """
        global _VADER_ANALYZER, _HF_SENTIMENT_PIPE

        if not reviews_text or not reviews_text.strip():
            return 0.0  # No review data — neutral

        # Truncate to keep inference fast; most review snippets fit in 512 tokens
        text = reviews_text.strip()[:1024]

        # ── Path 1: VADER ───────────────────────────────────────────────────────────
        if _VADER_ANALYZER is not None:
            try:
                scores = _VADER_ANALYZER.polarity_scores(text)
                return float(scores["compound"])  # already in [-1, 1]
            except Exception as exc:
                logger.warning("VADER scoring failed: %s", exc)

        # ── Path 2: HuggingFace pipeline (lazy-loaded) ───────────────────────────
        if _HF_SENTIMENT_PIPE is None:
            try:
                from transformers import pipeline as hf_pipeline  # noqa: PLC0415
                _HF_SENTIMENT_PIPE = hf_pipeline(
                    "sentiment-analysis",
                    model="distilbert-base-uncased-finetuned-sst-2-english",
                    truncation=True,
                    max_length=512,
                )
                logger.info("[Sentiment] Loaded HuggingFace distilbert-sst2 pipeline.")
            except Exception as exc:
                logger.warning("[Sentiment] Could not load HuggingFace pipeline: %s", exc)

        if _HF_SENTIMENT_PIPE is not None:
            try:
                result = _HF_SENTIMENT_PIPE(text[:512])[0]  # pipeline max_length guard
                # result = {"label": "POSITIVE"|"NEGATIVE", "score": 0.0–1.0}
                raw_score = float(result["score"])  # confidence in [0.5, 1.0]
                # Map to signed polarity:
                #   POSITIVE confidence 0.9 → +0.8,  NEGATIVE confidence 0.9 → -0.8
                polarity = (raw_score - 0.5) * 2  # [0, 1] range
                if result["label"] == "NEGATIVE":
                    polarity = -polarity
                return float(np.clip(polarity, -1.0, 1.0))
            except Exception as exc:
                logger.warning("HuggingFace sentiment inference failed: %s", exc)

        # ── Path 3: Neutral fallback ────────────────────────────────────────────────
        return 0.0

    def _calculate_content_scores(
        self, query_embedding: np.ndarray, items: List[Dict]
    ) -> List[float]:
        """Calculate cosine similarity between query embedding and each item embedding."""
        scores = []
        for item in items:
            item_embedding = self._get_item_embedding(item)
            try:
                similarity = cosine_similarity(
                    [query_embedding], [item_embedding]
                )[0][0]
            except Exception:
                similarity = 0.5

            # Compute a sentiment score from review text SEPARATELY from the embedding
            sentiment_score = self._calculate_sentiment_score(
                item.get("reviews_text", "") or ""
            )
            quality_boost = self._calculate_quality_boost(item, sentiment_score)
            genre_boost = self._calculate_genre_boost(item)
            final_score = float(similarity) * (1 + quality_boost + genre_boost)
            scores.append(min(final_score, 1.0))
        return scores

    def _get_item_embedding(self, item: Dict) -> np.ndarray:
        """
        Return a real embedding for the item.
        Uses the shared HuggingFace model if available, otherwise TF-IDF hash.

        Reviews are intentionally EXCLUDED from the embedding text.
        They are opinion-laden and pollute semantic similarity with sentiment words
        rather than thematic content. Sentiment is handled separately by
        ``_calculate_sentiment_score`` and fed into the quality multiplier.
        """
        text_parts = [item.get("title", "")]
        genres = item.get("genres", [])
        if isinstance(genres, list):
            text_parts.append(" ".join(genres))
        keywords = item.get("keywords", [])
        if isinstance(keywords, list):
            text_parts.append(" ".join(keywords[:10]))
        text_parts.append(item.get("overview", "")[:300])

        # NOTE: reviews_text is deliberately NOT appended here.
        # Raw review snippets were mixing semantic content with polarity words
        # ("brilliant", "dull"), causing the embedding to partially encode
        # sentiment instead of theme. Sentiment is now extracted explicitly via
        # _calculate_sentiment_score() and applied as a quality boost multiplier.

        text = ". ".join(p for p in text_parts if p)

        if self.embeddings_model and text.strip():
            try:
                vec = self.embeddings_model.embed_query(text)
                return np.array(vec, dtype=np.float32)
            except Exception as model_exc:
                warnings.warn(
                    f"[AdvancedRecommendationEngine] Primary embedding model failed for item "
                    f"'{item.get('title', 'unknown')}': {model_exc}. "
                    "Falling back to TF-IDF projection.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                logger.warning(
                    "Embedding model error for item '%s': %s — using TF-IDF fallback.",
                    item.get("title", "unknown"),
                    model_exc,
                )

        # ── TF-IDF fallback ────────────────────────────────────────────────────
        # A zero vector is *never* used: cosine_similarity(zeros, x) = 0 for all x,
        # which silently collapses every fallback item to the same score and
        # destroys ranking quality.
        #
        # Instead, build a deterministic, unit-normalised representation:
        #   1. Fit a char-level TF-IDF on the item text.
        #   2. Project the sparse vector into 384 dims via TruncatedSVD.
        #   3. If the text is too short for SVD, fall back to a seeded
        #      pseudo-random unit vector that is at least *unique* per item.
        if not text.strip():
            # Absolute last resort: deterministic unit vector seeded on title hash.
            seed = int(hashlib.md5(item.get("title", "unknown").encode()).hexdigest(), 16) % (2 ** 32)
            rng = np.random.default_rng(seed)
            vec = rng.standard_normal(384).astype(np.float32)
            norm = np.linalg.norm(vec)
            return vec / norm if norm > 0 else vec

        dim = 384
        try:
            vectorizer = TfidfVectorizer(
                analyzer="char_wb", ngram_range=(3, 5), max_features=min(2000, max(dim * 4, 1))
            )
            sparse_matrix = vectorizer.fit_transform([text])
            n_features = sparse_matrix.shape[1]
            n_components = min(dim, n_features - 1)  # SVD requires n_components < n_features

            if n_components > 0:
                svd = TruncatedSVD(n_components=n_components, random_state=42)
                dense = svd.fit_transform(sparse_matrix)[0].astype(np.float32)
                # Pad to 384 dims if n_components < dim
                if len(dense) < dim:
                    dense = np.pad(dense, (0, dim - len(dense)))
            else:
                raise ValueError("Not enough TF-IDF features for SVD projection.")
        except Exception as tfidf_exc:
            warnings.warn(
                f"[AdvancedRecommendationEngine] TF-IDF fallback also failed: {tfidf_exc}. "
                "Using seeded pseudo-random unit vector.",
                RuntimeWarning,
                stacklevel=2,
            )
            seed = int(hashlib.md5(text[:256].encode()).hexdigest(), 16) % (2 ** 32)
            rng = np.random.default_rng(seed)
            dense = rng.standard_normal(dim).astype(np.float32)

        norm = np.linalg.norm(dense)
        return dense / norm if norm > 0 else dense

    def _calculate_quality_boost(self, item: Dict, sentiment_score: float = 0.0) -> float:
        """
        Compute a quality multiplier for an item in the range [0.0, 0.65].

        Components
        ----------
        Rating boost (0 – 0.30)
            Based on the TMDB vote_average stored in ``item["rating"]``.

        Popularity boost (0 – 0.15)
            Based on the item's TMDB popularity score.

        Sentiment boost (−0.20 – +0.20)
            Based on ``sentiment_score``, a normalised polarity in [-1, 1]:
            * > +0.5  → strong positive boost  (+0.20)
            * > +0.1  → mild  positive boost    (+0.10)
            * < -0.5  → strong negative penalty (−0.20)
            * < -0.1  → mild  negative penalty  (−0.10)
            * otherwise → neutral (0)

        The total is clamped to 0.65 so that even a perfect item cannot
        dominate the relevance score entirely.
        """
        quality_score = 0.0

        # ── Rating boost ─────────────────────────────────────────────────────────────
        rating = item.get("rating", 0)
        if rating >= 8.5:
            quality_score += 0.30
        elif rating >= 7.5:
            quality_score += 0.20
        elif rating >= 6.5:
            quality_score += 0.10

        # ── Popularity boost ──────────────────────────────────────────────────────────
        popularity = item.get("popularity", 0)
        if popularity > 100:
            quality_score += 0.15
        elif popularity > 50:
            quality_score += 0.08

        # ── Sentiment boost / penalty ──────────────────────────────────────────────────
        # sentiment_score is in [-1.0, +1.0]:
        #   +1.0 → uniformly glowing reviews → max +0.20 boost
        #   -1.0 → uniformly panned reviews  → max -0.20 penalty
        if sentiment_score > 0.5:
            quality_score += 0.20
        elif sentiment_score > 0.1:
            quality_score += 0.10
        elif sentiment_score < -0.5:
            quality_score -= 0.20
        elif sentiment_score < -0.1:
            quality_score -= 0.10
        # Neutral band (-0.1 to +0.1): no adjustment

        return min(quality_score, 0.65)   # increased ceiling to 0.65 (was 0.50)

    def _calculate_genre_boost(self, item: Dict) -> float:
        return 0.1  # Neutral; user-specific boost would require preference data

    def _calculate_collaborative_scores(
        self,
        user_id: str,
        items: List[Dict],
        user_interactions: List[Dict],
        item_features: Dict,
    ) -> List[float]:
        if not user_interactions:
            return [0.5] * len(items)

        user_item_matrix = self._build_user_item_matrix(user_interactions)
        similar_users = self._find_similar_users(user_id, user_item_matrix)
        scores = []

        for item in items:
            user_based = self._user_based_score(item, similar_users, user_item_matrix)
            item_based = self._item_based_score(item, user_id, user_interactions)
            mf_score = self._matrix_factorization_score(item, user_id, user_interactions)
            collab_score = 0.4 * user_based + 0.3 * item_based + 0.3 * mf_score
            scores.append(collab_score)

        return scores

    def _calculate_trending_scores(self, items: List[Dict]) -> List[float]:
        scores = []
        current_year = datetime.now().year

        for item in items:
            score = 0.5
            release_year = self._extract_year(item.get("release_date", ""))
            if release_year:
                recency_boost = max(0, (current_year - release_year) / 10)
                score += (1 - recency_boost) * self.trending_weights['recency']

            popularity = item.get("popularity", 0)
            if popularity > 0:
                popularity_boost = min(popularity / 1000, 1.0)
                score += popularity_boost * self.trending_weights['popularity']

            engagement_score = item.get("engagement_score", 0.5)
            score += engagement_score * self.trending_weights['user_engagement']
            scores.append(min(score, 1.0))

        return scores

    def _calculate_serendipity_score(self, item: Dict, user_preferences: Dict) -> float:
        item_genres = set(item.get("genres", []))
        item_keywords = set(item.get("keywords", []))
        user_genres = set(user_preferences.get("genres", []))
        user_keywords = set(user_preferences.get("keywords", []))

        genre_novelty = 1 - len(item_genres.intersection(user_genres)) / max(len(item_genres), 1)
        keyword_novelty = 1 - len(item_keywords.intersection(user_keywords)) / max(len(item_keywords), 1)

        # Use sentiment-aware quality boost so critically loved hidden gems
        # can still surface even when they are far outside the user's usual genres
        sentiment_score = self._calculate_sentiment_score(
            item.get("reviews_text", "") or ""
        )
        quality_score = self._calculate_quality_boost(item, sentiment_score)

        return genre_novelty * 0.4 + keyword_novelty * 0.3 + quality_score * 0.3

    def _generate_serendipity_reason(self, item: Dict, user_preferences: Dict) -> str:
        item_genres = set(item.get("genres", []))
        user_genres = set(user_preferences.get("genres", []))
        new_genres = item_genres - user_genres

        if new_genres:
            return f"Explore {list(new_genres)[0]} — you might discover a new favourite genre!"
        elif item.get("rating", 0) > 8.0:
            return "Critically acclaimed title that expands your horizons"
        return "A hidden gem that breaks the mould of your usual preferences"

    def _build_user_item_matrix(self, interactions: List[Dict]) -> Dict:
        matrix = defaultdict(dict)
        for interaction in interactions:
            user_id = interaction.get("user_id")
            item_id = interaction.get("tmdb_id")
            interaction_type = interaction.get("interaction_type")
            rating = self._interaction_to_rating(interaction_type, interaction.get("rating"))
            if user_id and item_id:
                matrix[user_id][item_id] = rating
        return dict(matrix)

    def _interaction_to_rating(self, interaction_type: str, explicit_rating: Optional[int] = None) -> float:
        if interaction_type == "rate" and explicit_rating:
            return float(explicit_rating) / 2.0  # Convert 1-10 to 1-5 scale
        ratings = {
            "like": 4.0, "love": 5.0, "watch": 3.5,
            "dislike": 1.0, "skip": 2.0,
        }
        return ratings.get(interaction_type, 3.0)

    def _find_similar_users(self, user_id: str, user_item_matrix: Dict) -> List[Tuple[str, float]]:
        if user_id not in user_item_matrix:
            return []
        target_items = user_item_matrix[user_id]
        similar = []
        for other_id, other_items in user_item_matrix.items():
            if other_id == user_id:
                continue
            sim = self._calculate_user_similarity(target_items, other_items)
            if sim > 0.1:
                similar.append((other_id, sim))
        similar.sort(key=lambda x: x[1], reverse=True)
        return similar[:10]

    def _calculate_user_similarity(self, u1: Dict, u2: Dict) -> float:
        common = set(u1.keys()).intersection(set(u2.keys()))
        if not common:
            return 0.0
        r1 = [u1[i] for i in common]
        r2 = [u2[i] for i in common]
        return float(cosine_similarity([r1], [r2])[0][0])

    def _user_based_score(
        self, item: Dict, similar_users: List[Tuple[str, float]], user_item_matrix: Dict
    ) -> float:
        item_id = str(item.get("id"))
        score = total_sim = 0.0
        for similar_uid, similarity in similar_users:
            item_ratings = user_item_matrix.get(similar_uid, {})
            if item_id in item_ratings:
                score += similarity * item_ratings[item_id]
                total_sim += similarity
        return score / total_sim if total_sim > 0 else 0.5

    # ── ALS Matrix Factorization helpers ───────────────────────────────────────────

    @staticmethod
    def _matrix_to_csr(
        user_item_dict: Dict[str, Dict],
    ) -> Tuple["sp.csr_matrix", Dict[str, int], Dict[int, str], Dict[str, int], Dict[int, str]]:
        """
        Convert the nested dict ``{user_id: {item_id: rating}}`` produced by
        ``_build_user_item_matrix`` into a SciPy CSR sparse matrix and the
        bidirectional index mappings required by the ALS model.

        Returns
        -------
        csr         : items × users CSR matrix  (implicit expects item-major)
        user2idx    : str user_id  → int column index
        idx2user    : int column index  → str user_id
        item2idx    : str item_id  → int row index
        idx2item    : int row index  → str item_id
        """
        # Build contiguous integer indices for every user and item seen
        user_ids = sorted(user_item_dict.keys())
        item_ids = sorted(
            {str(iid) for u_ratings in user_item_dict.values() for iid in u_ratings}
        )

        user2idx: Dict[str, int] = {u: i for i, u in enumerate(user_ids)}
        idx2user: Dict[int, str] = {i: u for u, i in user2idx.items()}
        item2idx: Dict[str, int] = {it: i for i, it in enumerate(item_ids)}
        idx2item: Dict[int, str] = {i: it for it, i in item2idx.items()}

        rows, cols, data = [], [], []
        for user, ratings in user_item_dict.items():
            u_idx = user2idx[user]
            for item_id, rating in ratings.items():
                i_idx = item2idx[str(item_id)]
                rows.append(i_idx)     # item row
                cols.append(u_idx)     # user column
                data.append(float(rating))

        n_items = len(item_ids)
        n_users = len(user_ids)
        csr = sp.csr_matrix((data, (rows, cols)), shape=(n_items, n_users), dtype=np.float32)
        return csr, user2idx, idx2user, item2idx, idx2item

    def _build_als_model(
        self,
        user_item_dict: Dict[str, Dict],
        factors: int = 32,
        iterations: int = 15,
        regularization: float = 0.01,
    ):
        """
        Train a lightweight ALS model on the interaction matrix derived from
        *user_item_dict*.  The result is cached on the instance so that repeated
        calls within the same request do not retrain unnecessarily.

        The cache key is a frozenset fingerprint of ``(user_id, item_id, rating)``
        triples, so the model is automatically rebuilt whenever the interaction
        data changes.

        Parameters
        ----------
        factors        : Number of latent dimensions (32 is fast and sufficient for
                         small-to-medium corpora).
        iterations     : ALS alternating steps (15 is enough for convergence at this scale).
        regularization : L2 penalty to prevent overfitting on sparse data.

        Returns
        -------
        (model, user2idx, idx2user, item2idx, idx2item)
        or ``None`` if implicit is not installed or the matrix is too small.
        """
        if not _ALS_AVAILABLE:
            return None

        # Produce a stable fingerprint of the current interaction set
        fingerprint = frozenset(
            (u, str(iid), v)
            for u, ratings in user_item_dict.items()
            for iid, v in ratings.items()
        )

        # Serve the cached model if the interaction data hasn't changed
        cached = getattr(self, "_als_cache", None)
        if cached is not None and cached["key"] == fingerprint:
            return cached["model"]

        try:
            csr, user2idx, idx2user, item2idx, idx2item = self._matrix_to_csr(user_item_dict)

            # ALS needs at least 2 users and 2 items
            if csr.shape[0] < 2 or csr.shape[1] < 2:
                return None

            model = _ALS(
                factors=min(factors, csr.shape[1] - 1),  # factors must be < n_users
                iterations=iterations,
                regularization=regularization,
                use_gpu=False,
                calculate_training_loss=False,
            )
            # implicit ≥0.7 expects a user × items matrix for fit()
            model.fit(csr.T.tocsr(), show_progress=False)

            result = {
                "key": fingerprint,
                "model": (model, user2idx, idx2user, item2idx, idx2item),
            }
            self._als_cache = result
            logger.info(
                "[MF] ALS model trained: %d users × %d items, %d factors.",
                csr.shape[1], csr.shape[0], model.factors,
            )
            return result["model"]

        except Exception as exc:
            logger.warning("[MF] ALS training failed: %s", exc)
            return None

    def _item_based_score(self, item: Dict, user_id: str, user_interactions: List[Dict]) -> float:
        """
        Item-based collaborative score using ALS item latent factors.

        For each item the user has previously interacted with, compute the cosine
        similarity between that item's ALS latent-factor vector and the candidate
        item's latent-factor vector.  Return the weighted average, where the weight
        is the user's implicit rating for the interacted item.

        Falls back to 0.5 (neutral) on cold-start or when implicit is unavailable.
        """
        if not user_interactions or not _ALS_AVAILABLE:
            return 0.5

        user_item_matrix = self._build_user_item_matrix(user_interactions)
        als_result = self._build_als_model(user_item_matrix)
        if als_result is None:
            return 0.5

        model, user2idx, idx2user, item2idx, idx2item = als_result
        candidate_id = str(item.get("id", ""))

        if candidate_id not in item2idx:
            return 0.5  # cold-start: item not seen during training

        candidate_idx = item2idx[candidate_id]
        # item_factors: shape (n_items, factors)
        candidate_vec = model.item_factors[candidate_idx].reshape(1, -1)

        user_rated = user_item_matrix.get(user_id, {})
        if not user_rated:
            return 0.5

        total_weight = weighted_sim = 0.0
        for rated_id, rating in user_rated.items():
            rid = str(rated_id)
            if rid == candidate_id or rid not in item2idx:
                continue
            rated_vec = model.item_factors[item2idx[rid]].reshape(1, -1)
            sim = float(cosine_similarity(candidate_vec, rated_vec)[0][0])
            # Weight positive interactions more heavily than neutral or negative ones
            w = max(rating, 0.1)
            weighted_sim += sim * w
            total_weight += w

        if total_weight == 0:
            return 0.5

        raw = weighted_sim / total_weight           # in roughly [-1, 1]
        normalised = (raw + 1.0) / 2.0             # shift to [0, 1]
        return float(np.clip(normalised, 0.0, 1.0))

    def _matrix_factorization_score(self, item: Dict, user_id: str, user_interactions: List[Dict]) -> float:
        """
        Matrix-factorization score via ALS latent-factor dot product.

        Retrieves the user vector ``p_u`` and item vector ``q_i`` from the trained
        ALS model and returns ``sigmoid(p_u ⋅ q_i)`` as a score in (0, 1).  The
        sigmoid maps the raw dot product from an unbounded range into a smooth
        probability-like output, which mixes cleanly with the other score components.

        Falls back to 0.5 (neutral) on cold-start or when implicit is unavailable.
        """
        if not user_interactions or not _ALS_AVAILABLE:
            return 0.5

        user_item_matrix = self._build_user_item_matrix(user_interactions)
        als_result = self._build_als_model(user_item_matrix)
        if als_result is None:
            return 0.5

        model, user2idx, idx2user, item2idx, idx2item = als_result
        candidate_id = str(item.get("id", ""))

        if candidate_id not in item2idx:
            return 0.5  # cold-start
        if user_id not in user2idx:
            return 0.5  # new user with no ALS vector yet

        user_idx = user2idx[user_id]
        item_idx = item2idx[candidate_id]

        # user_factors: shape (n_users, factors)   item_factors: shape (n_items, factors)
        p_u = model.user_factors[user_idx]   # latent preference vector
        q_i = model.item_factors[item_idx]   # latent item attribute vector

        dot = float(np.dot(p_u, q_i))

        # Sigmoid maps (-∞, +∞) → (0, 1) smoothly
        sigmoid = 1.0 / (1.0 + np.exp(-dot))
        return float(np.clip(sigmoid, 0.0, 1.0))

    def _calculate_diversity_score(self, item: Dict, selected_items: List[Dict]) -> float:
        if not selected_items:
            return 1.0
        similarities = []
        for sel in selected_items:
            g1, g2 = set(item.get("genres", [])), set(sel.get("genres", []))
            k1, k2 = set(item.get("keywords", [])), set(sel.get("keywords", []))
            genre_sim = self._jaccard_similarity(g1, g2)
            keyword_sim = self._jaccard_similarity(k1, k2)
            similarities.append(genre_sim * 0.6 + keyword_sim * 0.4)
        return 1 - max(similarities)

    def _jaccard_similarity(self, s1: set, s2: set) -> float:
        if not s1 and not s2:
            return 1.0
        inter = len(s1.intersection(s2))
        union = len(s1.union(s2))
        return inter / union if union > 0 else 0.0

    def _extract_year(self, date_string: str) -> Optional[int]:
        if not date_string or str(date_string) in ("nan", "None", ""):
            return None
        try:
            return int(str(date_string)[:4])
        except (ValueError, TypeError):
            return None

    def _extract_user_preferences(self, user_history: List[Dict]) -> Dict:
        preferences = {"genres": [], "keywords": [], "liked_items": [], "disliked_items": []}
        for interaction in user_history:
            if interaction.get("interaction_type") in ("like", "love"):
                preferences["genres"].extend(interaction.get("genres") or [])
                preferences["keywords"].extend(interaction.get("keywords") or [])
                preferences["liked_items"].append(interaction.get("tmdb_id"))
            elif interaction.get("interaction_type") == "dislike":
                preferences["disliked_items"].append(interaction.get("tmdb_id"))
        return preferences