import numpy as np
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Embeddings
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os
import requests
import google.generativeai as genai

# New Imports for PostgreSQL
from database import SessionLocal, Media, Interaction


# ── Gemini Embedding Wrapper ──────────────────────────────────────────────────

class GeminiEmbedder(Embeddings):
    """
    Thin LangChain-compatible wrapper around Google's embedding-001 model.
    Implements the same .embed_query / .embed_documents interface as
    HuggingFaceEmbeddings so the rest of the engine is unaware of the switch.

    Gemini embedding-001 outputs 768-dimensional vectors.  If you rebuild the
    FAISS index while using Gemini embeddings, the index dimension will be 768
    rather than 384 — make sure data_ingestor.py uses the same embedder.
    """

    def __init__(self, model: str = "models/embedding-001", task_type: str = "RETRIEVAL_QUERY"):
        self.model = model
        self.task_type = task_type

    def embed_query(self, text: str) -> list:
        result = genai.embed_content(
            model=self.model,
            content=text,
            task_type=self.task_type,
        )
        return result["embedding"]

    def embed_documents(self, texts: list) -> list:
        return [
            genai.embed_content(
                model=self.model,
                content=t,
                task_type="RETRIEVAL_DOCUMENT",
            )["embedding"]
            for t in texts
        ]

class RecommendationEngine:
    def __init__(self):
        # Configure Gemini first (needed for both embeddings and generation)
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-pro')
        else:
            self.gemini_model = None
            print("[WARNING] GEMINI_API_KEY not found — Gemini generation unavailable.")

        # ── Embedding Model Selection ─────────────────────────────────────────
        # Priority: Gemini embedding-001 (if key available) → HuggingFace fallback
        if gemini_api_key:
            try:
                self.embeddings = GeminiEmbedder(model="models/embedding-001")
                # Warm up with a test call to verify the key works
                self.embeddings.embed_query("test")
                print("[RecommendationEngine] Using Gemini embeddings (models/embedding-001)")
            except Exception as e:
                print(f"[RecommendationEngine] Gemini embeddings failed ({e}) — falling back to HuggingFace.")
                self.embeddings = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                )
        else:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            print("[RecommendationEngine] Using HuggingFace embeddings (paraphrase-multilingual-MiniLM-L12-v2)")

        # TMDB config
        self.tmdb_api_key = os.environ.get("TMDB_API_KEY")
        if not self.tmdb_api_key:
            print("[WARNING] TMDB_API_KEY not found in environment variables. Streaming platforms will not be available.")

        try:
            # SECURITY NOTE: allow_dangerous_deserialization is intentionally omitted.
            # The FAISS index at ../data/faiss_index is a trusted build artifact produced
            # by data_ingestor.py in this project. Never load FAISS indexes from
            # untrusted or user-supplied paths without re-enabling the flag explicitly.
            self.vector_store = FAISS.load_local(
                "../data/faiss_index",
                self.embeddings
            )
            # We no longer load the CSV here. We use PostgreSQL.
        except Exception as e:
            print("[WARNING] Could not load FAISS index. Did you run data_ingestor.py first?")
            raise e

    def _calculate_diversity_score(self, movie_overview, selected_overviews):
        """Calculate diversity score based on content similarity with already selected movies."""
        if not selected_overviews:
            return 1.0
        
        vectorizer = TfidfVectorizer(stop_words='english', max_features=100)
        try:
            all_texts = selected_overviews + [movie_overview]
            tfidf_matrix = vectorizer.fit_transform(all_texts)
            similarities = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])
            max_sim = similarities.max()
            return 1 - max_sim
        except:
            return 0.5

    def _generate_explanation(self, query, movies, similarities):
        """Generate a personalized explanation via Gemini."""
        if not self.gemini_model:
            return "AI explanation unavailable: GEMINI_API_KEY missing from .env"
        
        movie_titles = [m['title'] for m in movies]
        prompt = (f"You are an AI movie and TV recommendation expert. "
                  f"The user is searching for: '{query}'. "
                  f"I have selected these titles for them: {', '.join(movie_titles)}. "
                  f"Write a short, engaging explanation (2-3 sentences max) explaining why these titles are a great fit for their query. "
                  f"Do not list the titles individually, just explain the thematic connection.")
        try:
            response = self.gemini_model.generate_content(prompt)
            return f"🤖 **Movie and TV Shows Recommending Engine AI Says:**\n\n{response.text}"
        except Exception as e:
            return f"Failed to generate explanation: {str(e)}"

    def get_watch_providers(
        self,
        tmdb_id: int,
        media_type: str = "movie",
        regions: list = None,
    ) -> list:
        """
        Fetch streaming availability from TMDB's /watch/providers endpoint.

        TMDB's watch provider data is sourced directly from JustWatch — this is
        the officially sanctioned way to consume JustWatch data per their
        partnership agreement.  Calling JustWatch's private API directly would
        violate their ToS.

        Returns a list of dicts:
          [{"provider": "Netflix", "type": "flatrate", "region": "US"}, ...]

        The frontend can group by region for per-country availability badges.
        """
        if not self.tmdb_api_key:
            return []

        if regions is None:
            regions = ["US", "IN", "GB", "CA", "AU"]

        endpoint = "movie" if media_type == "movie" else "tv"
        url = f"https://api.themoviedb.org/3/{endpoint}/{tmdb_id}/watch/providers"

        try:
            response = requests.get(
                url,
                params={"api_key": self.tmdb_api_key},
                timeout=5,
            )
            if response.status_code != 200:
                return []

            results = response.json().get("results", {})
            providers = []
            seen = set()  # deduplicate across regions

            for region in regions:
                region_data = results.get(region, {})
                for stream_type in ["flatrate", "free", "ads", "rent", "buy"]:
                    for p in region_data.get(stream_type, []):
                        name = p.get("provider_name", "").strip()
                        if not name:
                            continue
                        key = (name, stream_type, region)
                        if key not in seen:
                            seen.add(key)
                            providers.append({
                                "provider": name,
                                "type": stream_type,
                                "region": region,
                                "logo_path": p.get("logo_path"),
                                "source": "JustWatch via TMDB",
                            })

            return providers

        except Exception as e:
            print(f"[watch_providers] Error fetching providers for {tmdb_id}: {e}")
            return []


    def get_recommendations(self, query: str, top_k: int = 15, final_results: int = 6, 
                            user_id: str = None, genre: str = None, 
                            min_rating: float = 0.0, media_type: str = "All"):
        """
        Get personalized recommendations using FAISS, filters, and PostgreSQL metadata.

        The embedding model (paraphrase-multilingual-MiniLM-L12-v2) is natively
        multilingual: non-English queries are mapped directly into the same vector
        space as English content, so translation is both unnecessary and harmful
        (it introduces latency and translation noise).
        """
        # Pass the raw query directly — no translation needed.
        original_query = query

        # Fetch user interactions for hybrid scoring if user_id is provided
        user_likes = []
        user_dislikes = []
        db = SessionLocal()
        
        if user_id:
            interactions = db.query(Interaction).filter(Interaction.user_id == user_id).all()
            user_likes = [i.tmdb_id for i in interactions if i.interaction_type == "like"]
            user_dislikes = [i.tmdb_id for i in interactions if i.interaction_type == "dislike"]

        # Search using raw (potentially non-English) query.
        # top_k is doubled when post-filters are active so we have enough candidates.
        search_k = top_k * 2 if (min_rating > 0 or genre or media_type != "All") else top_k
        docs_with_scores = self.vector_store.similarity_search_with_score(query, k=search_k)
        
        candidates = []
        
        for doc, similarity_score in docs_with_scores:
            tmdb_id = doc.metadata.get("id")
            doc_media_type = doc.metadata.get("media_type", "movie")
            
            # Pre-filter by media_type
            if media_type != "All" and doc_media_type != media_type.lower().replace(" shows", ""):
                 continue
                 
            # Fetch metadata from PostgreSQL
            media_record = db.query(Media).filter(Media.tmdb_id == tmdb_id, Media.media_type == doc_media_type).first()
            
            if media_record:
                # Pre-filters
                if media_record.rating < min_rating:
                    continue
                if genre and genre.lower() not in (media_record.overview or "").lower(): # basic genre filter on description
                    continue
                    
                # Hybrid Collaborative Filtering Score
                # If the user liked similar things, we boost it.
                # Disliked items receive a penalty but are NOT hard-excluded so that
                # semantically exceptional results can still surface.
                collab_boost = 0.0
                if int(media_record.tmdb_id) in user_likes:
                    collab_boost = 0.2
                elif int(media_record.tmdb_id) in user_dislikes:
                    collab_boost = -0.3  # Negative penalty; combined_score may still be positive

                # FAISS similarity_search_with_score returns L2 (Euclidean) distance:
                # lower distance = more similar.  Convert to a [0, 1] similarity
                # score so that higher always means better, consistent with rating
                # and collaborative boost terms.
                semantic_similarity = 1.0 / (1.0 + similarity_score)  # maps [0, ∞) → (0, 1]

                # Calculate combined score: semantic similarity (70%) + rating boost (30%) + collab_boost
                normalized_rating = (media_record.rating or 0) / 10.0  # Normalize to 0-1
                combined_score = (semantic_similarity * 0.7) + (normalized_rating * 0.3) + collab_boost
                
                candidates.append({
                    "id": int(media_record.tmdb_id),
                    "db_id": int(media_record.db_id),
                    "title": media_record.title,
                    "overview": media_record.overview,
                    "release_date": media_record.release_date,
                    "rating": float(media_record.rating),
                    "poster_path": media_record.poster_path,
                    "media_type": media_record.media_type,
                    "similarity_score": float(semantic_similarity),  # store converted similarity, not raw L2
                    "combined_score": float(combined_score),
                    "original_doc": doc
                })
        
        db.close()
        
        # All score components (semantic_similarity, normalized_rating, collab_boost) are now
        # oriented as "higher is better", so a standard descending sort is correct.
        candidates.sort(key=lambda x: x["combined_score"], reverse=True)
        
        # Diversity filtering: Select diverse items using Maximal Marginal Relevance
        selected_media = []
        selected_overviews = []
        similarity_scores = []
        
        if candidates:
            top = candidates[0]
            selected_media.append(top)
            selected_overviews.append(top["overview"])
            similarity_scores.append(top["similarity_score"])
        
        remaining_candidates = candidates[1:]
        
        while len(selected_media) < final_results and remaining_candidates:
            best_diverse_candidate = None
            best_mmr_score = -1
            
            for candidate in remaining_candidates:
                lambda_param = 0.7  # Weight for relevance
                relevance = candidate["combined_score"]
                diversity = self._calculate_diversity_score(candidate["overview"], selected_overviews)
                mmr_score = lambda_param * relevance + (1 - lambda_param) * diversity
                
                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_diverse_candidate = candidate
            
            if best_diverse_candidate:
                selected_media.append(best_diverse_candidate)
                selected_overviews.append(best_diverse_candidate["overview"])
                similarity_scores.append(best_diverse_candidate["similarity_score"])
                remaining_candidates.remove(best_diverse_candidate)
            else:
                break
        
        # Generate explanation based on ORIGINAL query
        explanation = self._generate_explanation(original_query, selected_media, similarity_scores)
        
        # Clean up output and get watch providers
        output = []
        for m in selected_media:
            providers = self.get_watch_providers(m["id"], m["media_type"])
            
            # Format poster path correctly
            poster_url = ""
            if m["poster_path"] and not str(m["poster_path"]) == "nan":
                poster_url = f"https://image.tmdb.org/t/p/w500{m['poster_path']}"
                
            output.append({
                "id": m["id"],
                "title": m["title"],
                "overview": m["overview"],
                "release_date": m["release_date"],
                "rating": m["rating"],
                "poster_path": poster_url,
                "media_type": m["media_type"],
                "match_score": min(round(m["similarity_score"] * 100, 1), 100.0),
                "providers": providers
            })
            
        return {
            "explanation": explanation,
            "movies": output, # keep "movies" key for frontend compatibility
            "query": original_query,
            "total_candidates": len(candidates)
        }
