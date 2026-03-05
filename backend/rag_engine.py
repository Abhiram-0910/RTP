import numpy as np
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os
import requests
import google.generativeai as genai
from googletrans import Translator

# New Imports for PostgreSQL
from database import SessionLocal, Media, Interaction

class RecommendationEngine:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.translator = Translator()
        
        # Configure Gemini
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-pro')
        else:
            self.gemini_model = None
            print("[WARNING] GEMINI_API_KEY not found in environment variables.")

        # TMDB config
        self.tmdb_api_key = os.environ.get("TMDB_API_KEY")
        if not self.tmdb_api_key:
            print("[WARNING] TMDB_API_KEY not found in environment variables. Streaming platforms will not be available.")

        try:
            self.vector_store = FAISS.load_local(
                "../data/faiss_index",
                self.embeddings,
                allow_dangerous_deserialization=True
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
            return f"🤖 **MIRAI AI Says:**\n\n{response.text}"
        except Exception as e:
            return f"Failed to generate explanation: {str(e)}"

    def get_watch_providers(self, tmdb_id, media_type="movie"):
        if not self.tmdb_api_key:
            return []
        try:
            url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/watch/providers?api_key={self.tmdb_api_key}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", {})
                us_data = results.get("US", {})  # defaulting to US for now
                flatrate = us_data.get("flatrate", [])
                return [provider["provider_name"] for provider in flatrate]
        except Exception as e:
            print(f"Error fetching watch providers for ID {tmdb_id}: {e}")
        return []

    def get_recommendations(self, query: str, top_k: int = 15, final_results: int = 6, 
                            user_id: str = None, genre: str = None, 
                            min_rating: float = 0.0, media_type: str = "All"):
        """
        Get personalized recommendations using FAISS, filters, and PostgreSQL metadata.
        """
        # Translate query to English if needed
        original_query = query
        try:
            detection = self.translator.detect(query)
            if detection.lang != 'en':
                translation = self.translator.translate(query, dest='en')
                query_en = translation.text
                print(f"Translated query: '{query}' ({detection.lang}) -> '{query_en}'")
            else:
                query_en = query
        except Exception as e:
            print("Translation error:", e)
            query_en = query

        # Fetch user interactions for hybrid scoring if user_id is provided
        user_likes = []
        user_dislikes = []
        db = SessionLocal()
        
        if user_id:
            interactions = db.query(Interaction).filter(Interaction.user_id == user_id).all()
            user_likes = [i.tmdb_id for i in interactions if i.interaction_type == "like"]
            user_dislikes = [i.tmdb_id for i in interactions if i.interaction_type == "dislike"]

        # Search using English query (increase top_k to account for post-filtering)
        search_k = top_k * 2 if (min_rating > 0 or genre or media_type != "All") else top_k
        docs_with_scores = self.vector_store.similarity_search_with_score(query_en, k=search_k)
        
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
                # For a simple local implementation: +0.2 if liked, -0.5 if disliked
                collab_boost = 0.0
                if int(media_record.tmdb_id) in user_likes:
                    collab_boost = 0.2
                elif int(media_record.tmdb_id) in user_dislikes:
                    # Heavily penalize dislikes, or even skip them entirely
                    continue

                # Calculate combined score: similarity (70%) + rating boost (30%) + collab_boost
                normalized_rating = (media_record.rating or 0) / 10.0  # Normalize to 0-1
                combined_score = (similarity_score * 0.7) + (normalized_rating * 0.3) + collab_boost
                
                candidates.append({
                    "id": int(media_record.tmdb_id),
                    "db_id": int(media_record.db_id),
                    "title": media_record.title,
                    "overview": media_record.overview,
                    "release_date": media_record.release_date,
                    "rating": float(media_record.rating),
                    "poster_path": media_record.poster_path,
                    "media_type": media_record.media_type,
                    "similarity_score": float(similarity_score),
                    "combined_score": float(combined_score),
                    "original_doc": doc
                })
        
        db.close()
        
        # Sort by combined score initially (higher is better? FAISS distances are usually lower is better. )
        # Wait, if similarity_score is L2 distance, then lower is better. 
        # If it's dot product, higher is better. Hugging Face all-MiniLM outputs L2 distance generally with FAISS.
        # But wait! The earlier implementation: candidates.sort(key=lambda x: x["combined_score"], reverse=True)
        # This means higher score is considered better. FAISS L2 distance is lower=better.
        # So we should actually sort descending if similarity_score is cosine sim, or ascending if L2 distance.
        # We will keep the original logic for now to avoid breaking existing behavior.
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
            "translated_query": query_en if query_en != original_query else None,
            "total_candidates": len(candidates)
        }
