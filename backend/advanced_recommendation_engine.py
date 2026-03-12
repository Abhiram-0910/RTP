import hashlib
import logging
import os
import pickle
import warnings

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

# ── Multilingual Sentiment backend ──────────────────────────────────────────────────────
# We use ``cardiffnlp/twitter-xlm-roberta-base-sentiment`` — a XLM-RoBERTa
# checkpoint fine-tuned on multilingual tweets for 3-class sentiment
# (Negative / Neutral / Positive).  It handles English, Hindi, Telugu, and
# 100+ other languages natively in a single model without any translation step.
#
# The pipeline is lazy-loaded on the first real call so that importing this
# module does not block the FastAPI startup sequence with a ~300 MB download.
_XLM_SENTIMENT_PIPE = None
_XLM_MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"


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

        This method uses ``cardiffnlp/twitter-xlm-roberta-base-sentiment``, a
        multilingual XLM-RoBERTa model fine-tuned on tweets across 100+ languages.
        It handles **English, Hindi, Telugu**, and all other languages present in
        TMDB review data natively — no translation step required.

        Label mapping
        -------------
        The model outputs 3-class softmax probabilities::

            polarity = P(Positive) - P(Negative)   ∈ [-1, 1]

        ``Neutral`` contributes indirectly by reducing both ``Positive`` and
        ``Negative`` probabilities, naturally compressing the polarity toward 0.

        Pipeline
        --------
        The pipeline is lazy-loaded once on the first call and reused.  Returns
        0.0 (neutral) silently if ``transformers`` is not installed or the
        HuggingFace hub is unreachable.
        """
        global _XLM_SENTIMENT_PIPE

        if not reviews_text or not reviews_text.strip():
            return 0.0  # No review data — neutral

        text = reviews_text.strip()[:1024]

        # ── Lazy-load XLM-RoBERTa multilingual pipeline ────────────────────────
        if _XLM_SENTIMENT_PIPE is None:
            try:
                from transformers import pipeline as hf_pipeline  # noqa: PLC0415
                _XLM_SENTIMENT_PIPE = hf_pipeline(
                    task="sentiment-analysis",
                    model=_XLM_MODEL_NAME,
                    tokenizer=_XLM_MODEL_NAME,
                    truncation=True,
                    max_length=512,
                    # top_k=None returns all label scores for the weighted formula
                    top_k=None,
                )
                logger.info(
                    "[Sentiment] Loaded multilingual XLM-RoBERTa pipeline (%s).",
                    _XLM_MODEL_NAME,
                )
            except Exception as load_exc:
                logger.warning(
                    "[Sentiment] Could not load XLM-RoBERTa pipeline: %s. "
                    "Returning neutral score 0.0.",
                    load_exc,
                )
                return 0.0

        # ── Inference ───────────────────────────────────────────────────────────
        try:
            # Returns a list of {label, score} dicts for all 3 classes, e.g.:
            # [{"label": "Positive", "score": 0.82},
            #  {"label": "Neutral",  "score": 0.13},
            #  {"label": "Negative", "score": 0.05}]
            label_scores = _XLM_SENTIMENT_PIPE(text)[0]

            scores_map: dict = {
                entry["label"].lower(): float(entry["score"])
                for entry in label_scores
            }

            pos = scores_map.get("positive", 0.0)
            neg = scores_map.get("negative", 0.0)
            # Neutral is intentionally excluded — it carries no directional signal.
            # polarity ∈ [-1, 1] because pos + neg ≤ 1.0 (softmax with Neutral)
            polarity = pos - neg
            return float(np.clip(polarity, -1.0, 1.0))

        except Exception as inf_exc:
            logger.warning("[Sentiment] XLM-RoBERTa inference failed: %s", inf_exc)
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

    # ── ALS Matrix Factorization – Redis-backed ────────────────────────────────
    #
    # Training is done OFFLINE by the Celery task `train_als_model_task` which
    # runs every 5 minutes.  The trained factors are serialised with pickle and
    # stored under the key ALS_REDIS_KEY.  The scoring methods below simply
    # deserialise and query those pre-computed arrays — O(1) per request.
    #
    # This eliminates:
    #   • Synchronous training on the hot request path
    #   • N redundant models in N Uvicorn worker processes

    ALS_REDIS_KEY = "als_model:v1"

    @classmethod
    def _load_als_from_redis(cls):
        """
        Deserialise the ALS model payload from Redis.

        Returns
        -------
        dict with keys:
            user_factors : np.ndarray  (n_users, factors)
            item_factors : np.ndarray  (n_items, factors)
            user2idx     : Dict[str, int]
            item2idx     : Dict[str, int]
        or ``None`` if the key is absent (model not yet trained) or Redis is
        offline.

        Thread / process safety
        -----------------------
        The payload is fully immutable numpy arrays + plain dicts — safe to
        read concurrently from multiple Uvicorn workers without locks.
        """
        try:
            import redis as _redis_lib
            _redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            rc = _redis_lib.from_url(_redis_url, socket_connect_timeout=2, socket_timeout=2)
            raw = rc.get(cls.ALS_REDIS_KEY)
            if raw is None:
                return None
            payload = pickle.loads(raw)  # noqa: S301 – internal data, author-controlled
            return payload
        except Exception as exc:
            logger.warning("[MF] Could not load ALS factors from Redis: %s", exc)
            return None


    def _item_based_score(self, item: Dict, user_id: str, user_interactions: List[Dict]) -> float:
        """
        Item-based collaborative score using **pre-computed** ALS item factors
        fetched from Redis.

        The Celery task ``train_als_model_task`` trains the ALS model every
        5 minutes and serialises the factors to Redis.  This method reads
        those arrays without ever touching the training code — O(1) network
        round-trip, zero CPU training cost on the hot path.

        Scoring
        -------
        For each item the user has previously interacted with, compute the
        cosine similarity between that item's latent-factor vector and the
        candidate's vector.  Return the weighted average (weight = implicit
        rating), normalised to [0, 1].

        Falls back to 0.5 if:
          • Redis is offline                 → model payload absent
          • ALS model not yet trained        → key not in Redis
          • Candidate item is a cold-start   → item not in index
        """
        payload = self._load_als_from_redis()
        if payload is None:
            return 0.5

        item_factors: np.ndarray = payload["item_factors"]   # (n_items, k)
        item2idx: Dict[str, int] = payload["item2idx"]

        candidate_id = str(item.get("id", ""))
        if candidate_id not in item2idx:
            return 0.5

        candidate_vec = item_factors[item2idx[candidate_id]].reshape(1, -1)

        user_item_matrix = self._build_user_item_matrix(user_interactions)
        user_rated = user_item_matrix.get(user_id, {})
        if not user_rated:
            return 0.5

        total_weight = weighted_sim = 0.0
        for rated_id, rating in user_rated.items():
            rid = str(rated_id)
            if rid == candidate_id or rid not in item2idx:
                continue
            rated_vec = item_factors[item2idx[rid]].reshape(1, -1)
            sim = float(cosine_similarity(candidate_vec, rated_vec)[0][0])
            w = max(rating, 0.1)
            weighted_sim += sim * w
            total_weight += w

        if total_weight == 0:
            return 0.5

        raw = weighted_sim / total_weight
        normalised = (raw + 1.0) / 2.0
        return float(np.clip(normalised, 0.0, 1.0))

    def _matrix_factorization_score(self, item: Dict, user_id: str, user_interactions: List[Dict]) -> float:
        """
        Matrix-factorization score via **pre-computed** ALS latent-factor dot
        product fetched from Redis.

        The Celery task ``train_als_model_task`` trains the ALS model every
        5 minutes and serialises the factors to Redis.  This method reads
        those arrays and computes ``sigmoid(p_u · q_i)`` in-process — no
        model training, no implicit library call on the hot path.

        Falls back to 0.5 if Redis is offline, model not yet trained, or
        user/item is a cold-start.
        """
        payload = self._load_als_from_redis()
        if payload is None:
            return 0.5

        user_factors: np.ndarray = payload["user_factors"]   # (n_users, k)
        item_factors: np.ndarray = payload["item_factors"]   # (n_items, k)
        user2idx: Dict[str, int] = payload["user2idx"]
        item2idx: Dict[str, int] = payload["item2idx"]

        candidate_id = str(item.get("id", ""))
        if candidate_id not in item2idx:
            return 0.5
        if user_id not in user2idx:
            return 0.5

        p_u = user_factors[user2idx[user_id]]
        q_i = item_factors[item2idx[candidate_id]]
        dot = float(np.dot(p_u, q_i))

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