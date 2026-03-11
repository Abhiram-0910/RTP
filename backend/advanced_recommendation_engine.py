import hashlib
import logging
import warnings

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


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

            quality_boost = self._calculate_quality_boost(item)
            genre_boost = self._calculate_genre_boost(item)
            final_score = float(similarity) * (1 + quality_boost + genre_boost)
            scores.append(min(final_score, 1.0))
        return scores

    def _get_item_embedding(self, item: Dict) -> np.ndarray:
        """
        Return a real embedding for the item.
        Uses the shared HuggingFace model if available, otherwise TF-IDF hash.
        """
        text_parts = [item.get("title", "")]
        genres = item.get("genres", [])
        if isinstance(genres, list):
            text_parts.append(" ".join(genres))
        keywords = item.get("keywords", [])
        if isinstance(keywords, list):
            text_parts.append(" ".join(keywords[:10]))
        text_parts.append(item.get("overview", "")[:300])

        # Append aggregated review snippets to enrich the embedding with critic/user sentiment
        reviews_text = item.get("reviews_text", "") or ""
        if reviews_text.strip():
            text_parts.append(reviews_text.strip()[:200])

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

    def _calculate_quality_boost(self, item: Dict) -> float:
        quality_score = 0.0
        rating = item.get("rating", 0)
        if rating >= 8.5:
            quality_score += 0.3
        elif rating >= 7.5:
            quality_score += 0.2
        elif rating >= 6.5:
            quality_score += 0.1

        popularity = item.get("popularity", 0)
        if popularity > 100:
            quality_score += 0.2
        elif popularity > 50:
            quality_score += 0.1

        return min(quality_score, 0.5)

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
        quality_score = self._calculate_quality_boost(item)

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

    def _item_based_score(self, item: Dict, user_id: str, user_interactions: List[Dict]) -> float:
        # Simplified item-based: 0.5 neutral (full SVD would require offline training)
        return 0.5

    def _matrix_factorization_score(self, item: Dict, user_id: str, user_interactions: List[Dict]) -> float:
        # Simplified: neutral score (full MF requires offline training)
        return 0.5

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