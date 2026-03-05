import google.generativeai as genai
import os
from typing import List, Dict, Optional
import json
import re
from datetime import datetime

class AIRecommendationExplainer:
    def __init__(self, api_key: str = None):
        """Initialize the AI explainer with Gemini API"""
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key is required")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        self.chat_model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Context memory for personalized explanations
        self.user_context = {}
        
    def generate_personalized_explanation(self, query: str, recommendations: List[Dict], 
                                        user_id: str = None, user_history: List[Dict] = None) -> str:
        """Generate personalized explanation using RAG and user context"""
        
        # Build user context if available
        user_profile = ""
        if user_id and user_history:
            user_profile = self._build_user_profile(user_history)
        
        # Create detailed prompt for explanation
        prompt = self._create_explanation_prompt(query, recommendations, user_profile)
        
        try:
            response = self.model.generate_content(prompt)
            explanation = response.text
            
            # Clean and format the explanation
            explanation = self._format_explanation(explanation, query, recommendations)
            
            # Store context for future personalization
            if user_id:
                self._update_user_context(user_id, query, recommendations)
            
            return explanation
            
        except Exception as e:
            return self._generate_fallback_explanation(query, recommendations)
    
    def _build_user_profile(self, user_history: List[Dict]) -> str:
        """Build a user profile based on interaction history"""
        liked_genres = []
        liked_themes = []
        disliked_items = []
        
        for interaction in user_history:
            if interaction.get("interaction_type") == "like":
                if "genres" in interaction:
                    liked_genres.extend(interaction["genres"])
                if "keywords" in interaction:
                    liked_themes.extend(interaction["keywords"])
            elif interaction.get("interaction_type") == "dislike":
                disliked_items.append(interaction.get("title", ""))
        
        # Get top genres and themes
        top_genres = self._get_top_items(liked_genres, 5)
        top_themes = self._get_top_items(liked_themes, 5)
        
        profile = f"""
User Profile:
- Preferred Genres: {', '.join(top_genres)}
- Interested Themes: {', '.join(top_themes)}
- Disliked: {len(disliked_items)} items
"""
        return profile
    
    def _get_top_items(self, items: List[str], limit: int) -> List[str]:
        """Get top items by frequency"""
        from collections import Counter
        counter = Counter(items)
        return [item for item, _ in counter.most_common(limit)]
    
    def _create_explanation_prompt(self, query: str, recommendations: List[Dict], user_profile: str) -> str:
        """Create detailed prompt for AI explanation"""
        
        # Extract key information from recommendations
        titles = [rec["title"] for rec in recommendations[:5]]
        genres = []
        themes = []
        ratings = []
        years = []
        
        for rec in recommendations[:5]:
            if "genres" in rec:
                genres.extend(rec["genres"])
            if "keywords" in rec:
                themes.extend(rec["keywords"])
            if "rating" in rec:
                ratings.append(rec["rating"])
            if "release_date" in rec and rec["release_date"]:
                years.append(rec["release_date"][:4])
        
        # Analyze query intent
        query_analysis = self._analyze_query_intent(query)
        
        prompt = f"""
You are MIRAI, an advanced AI movie and TV show recommendation expert with deep understanding of cinema, storytelling, and user preferences.

USER QUERY: "{query}"

{user_profile}

QUERY ANALYSIS:
{query_analysis}

RECOMMENDED TITLES: {', '.join(titles)}

KEY THEMES FOUND: {', '.join(set(themes[:8]))}

DOMINANT GENRES: {', '.join(set(genres[:5]))}

AVERAGE RATING: {sum(ratings)/len(ratings) if ratings else 'N/A'}

RELEASE YEARS: {min(years) if years else 'N/A'} - {max(years) if years else 'N/A'}

YOUR TASK:
Generate a compelling, personalized explanation (2-3 paragraphs) that:
1. Shows deep understanding of the user's query and intent
2. Explains why these specific titles are perfect matches
3. Highlights the common themes, genres, and elements that connect them
4. Uses cinematic language and references when appropriate
5. Feels personal and engaging, not generic
6. Mentions specific aspects like storytelling style, emotional impact, or technical excellence
7. If user profile exists, reference their preferences

Be specific, insightful, and avoid generic statements. Use vivid language that captures the essence of these recommendations.

EXPLANATION:
"""
        return prompt
    
    def _analyze_query_intent(self, query: str) -> str:
        """Analyze user query to understand intent"""
        query_lower = query.lower()
        
        # Define intent patterns
        intents = {
            "mood": ["mood", "feeling", "emotion", "vibe", "atmosphere"],
            "genre": ["thriller", "comedy", "drama", "action", "horror", "romance", "sci-fi", "fantasy"],
            "theme": ["mind-bending", "thought-provoking", "emotional", "inspiring", "dark", "light"],
            "style": ["visually stunning", "beautiful cinematography", "amazing visuals", "artistic"],
            "time": ["recent", "classic", "old", "new", "latest", "2020s", "90s", "80s"],
            "quality": ["masterpiece", "award-winning", "critically acclaimed", "highly rated"]
        }
        
        detected_intents = []
        for intent_type, keywords in intents.items():
            if any(keyword in query_lower for keyword in keywords):
                detected_intents.append(intent_type)
        
        return f"Detected intents: {', '.join(detected_intents) if detected_intents else 'general recommendation'}"
    
    def _format_explanation(self, explanation: str, query: str, recommendations: List[Dict]) -> str:
        """Format and enhance the AI explanation"""
        # Remove any markdown or formatting artifacts
        explanation = re.sub(r'\*+', '', explanation)
        explanation = re.sub(r'^\s+', '', explanation)
        explanation = re.sub(r'\s+$', '', explanation)
        
        # Add emojis and formatting
        explanation = explanation.replace("I recommend", "🎯 I recommend")
        explanation = explanation.replace("These films", "🎬 These films")
        explanation = explanation.replace("These shows", "📺 These shows")
        explanation = explanation.replace("These titles", "🎭 These titles")
        
        # Add signature
        explanation += f"\n\n✨ **MIRAI AI Analysis** - Personalized for your search: \"{query}\""
        
        return explanation
    
    def _update_user_context(self, user_id: str, query: str, recommendations: List[Dict]):
        """Update user context for future personalization"""
        if user_id not in self.user_context:
            self.user_context[user_id] = {
                "search_history": [],
                "preferred_genres": [],
                "preferred_themes": [],
                "last_activity": datetime.now()
            }
        
        # Add search to history
        self.user_context[user_id]["search_history"].append({
            "query": query,
            "timestamp": datetime.now(),
            "recommendations": [rec["title"] for rec in recommendations[:3]]
        })
        
        # Keep only recent history (last 50 searches)
        self.user_context[user_id]["search_history"] = self.user_context[user_id]["search_history"][-50:]
        
        self.user_context[user_id]["last_activity"] = datetime.now()
    
    def _generate_fallback_explanation(self, query: str, recommendations: List[Dict]) -> str:
        """Generate fallback explanation if AI fails"""
        titles = [rec["title"] for rec in recommendations[:3]]
        
        explanations = [
            f"🎯 Based on your search for '{query}', I've selected these titles that capture the essence of what you're looking for. Each one offers a unique perspective while staying true to your core interests.",
            f"🎬 These recommendations perfectly align with your query '{query}'. They share common themes and elements that should resonate with your current mood and preferences.",
            f"✨ Your search for '{query}' led me to these exceptional titles. Each one brings something special to the table while maintaining the spirit of what you're seeking."
        ]
        
        return explanations[0] + f"\n\n🎭 Featured: {', '.join(titles)}"
    
    def generate_trending_explanation(self, trending_movies: List[Dict], trending_shows: List[Dict]) -> str:
        """Generate explanation for trending content"""
        movie_titles = [movie["title"] for movie in trending_movies[:3]]
        show_titles = [show["title"] for show in trending_shows[:3]]
        
        prompt = f"""
Generate a brief, engaging explanation about what's trending right now in movies and TV shows.

Trending Movies: {', '.join(movie_titles)}
Trending TV Shows: {', '.join(show_titles)}

Create a 2-3 sentence explanation that:
1. Captures why these are trending
2. Mentions the buzz or cultural moment
3. Encourages exploration
4. Sounds current and relevant

Keep it casual, engaging, and informative.
"""
        
        try:
            response = self.chat_model.generate_content(prompt)
            return f"🔥 **Trending Now:** {response.text}"
        except:
            return "🔥 Check out what's trending right now in movies and TV shows!"
    
    def analyze_user_sentiment(self, reviews: List[str]) -> Dict:
        """Analyze sentiment from user reviews"""
        if not reviews:
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0}
        
        prompt = f"""
Analyze the sentiment of these user reviews:
{json.dumps(reviews, indent=2)}

Provide a JSON response with:
- "sentiment": "positive", "negative", or "neutral"
- "score": -1.0 to 1.0 (negative to positive)
- "confidence": 0.0 to 1.0 (how confident you are)
- "key_themes": list of main themes mentioned
- "recommendation": brief recommendation based on sentiment
"""
        
        try:
            response = self.chat_model.generate_content(prompt)
            result = json.loads(response.text)
            return result
        except:
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.5, "key_themes": [], "recommendation": "Unable to analyze sentiment"}
    
    def generate_diversity_explanation(self, selected_titles: List[Dict], diversity_score: float) -> str:
        """Generate explanation about recommendation diversity"""
        titles = [title["title"] for title in selected_titles[:4]]
        
        if diversity_score > 0.8:
            diversity_level = "highly diverse"
            emoji = "🌈"
        elif diversity_score > 0.6:
            diversity_level = "well-balanced"
            emoji = "⚖️"
        else:
            diversity_level = "focused"
            emoji = "🎯"
        
        prompt = f"""
These {len(titles)} recommendations are {diversity_level} ({diversity_score:.1%} diversity score).

Titles: {', '.join(titles)}

Write a brief sentence explaining why this {diversity_level} selection benefits the user.
Keep it under 20 words, use {emoji} emoji, and make it sound helpful.
"""
        
        try:
            response = self.chat_model.generate_content(prompt)
            return response.text.strip()
        except:
            return f"{emoji} A {diversity_level} mix to broaden your viewing experience!"

# Global instance for easy access
ai_explainer = None

def get_ai_explainer():
    """Get or create the global AI explainer instance"""
    global ai_explainer
    if ai_explainer is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            ai_explainer = AIRecommendationExplainer(api_key)
        else:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
    return ai_explainer