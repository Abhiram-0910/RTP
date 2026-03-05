import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional

class EnhancedMovieApp:
    def __init__(self):
        self.api_base_url = "http://127.0.0.1:8000/api"
        self.user_id = "demo_user"
        self.watchlist = []
        self.recent_searches = []
        self.user_preferences = {}
        # Initialize filters with defaults to prevent AttributeError
        self.filters = {
            'media_type': "All",
            'min_rating': 6.0,
            'year_range': (1990, 2024),
            'max_runtime': 180,
            'genres': [],
            'platforms': [],
            'explanation_style': "Detailed Analysis",
            'diversity_level': 0.7,
            'include_trending': True,
            'language_pref': "Auto-detect"
        }
        
    def render_enhanced_ui(self):
        """Render the enhanced Streamlit UI"""
        st.set_page_config(
            page_title="MIRAI AI - Revolutionary Movie Discovery",
            page_icon="🎬",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Custom CSS for enhanced UI
        self._apply_enhanced_styles()
        
        # Header with AI branding
        self._render_header()
        
        # Main content area
        col1, col2 = st.columns([1, 3])
        
        with col1:
            self._render_enhanced_sidebar()
        
        with col2:
            self._render_main_content()
    
    def _apply_enhanced_styles(self):
        """Apply enhanced CSS styling"""
        st.markdown("""
        <style>
        /* Enhanced styling for MIRAI AI */
        .stApp {
            background-color: #0f172a;
            background-image: radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
                              radial-gradient(at 100% 0%, rgba(139, 92, 246, 0.15) 0px, transparent 50%);
            color: #f8fafc;
        }
        
        .mirai-header {
            background: linear-gradient(to right, #818cf8, #c084fc, #f472b6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 3.5rem !important;
            font-weight: 800 !important;
            text-align: center;
            margin-bottom: 0.5rem;
            text-shadow: 0 0 30px rgba(129, 140, 248, 0.3);
            padding-bottom: 15px;
        }
        
        .mirai-subtitle {
            text-align: center;
            color: #cbd5e1;
            font-size: 1.3rem;
            margin-bottom: 2rem;
            font-weight: 300;
            letter-spacing: 0.5px;
        }
        
        .ai-card {
            background: rgba(30, 41, 59, 0.9);
            border: 1px solid rgba(129, 140, 248, 0.3);
            border-radius: 16px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        
        .movie-card-enhanced {
            background: rgba(30, 41, 59, 0.8);
            border-radius: 12px;
            padding: 1rem;
            margin: 0.5rem 0;
            border: 1px solid rgba(129, 140, 248, 0.1);
            transition: all 0.3s ease;
            height: 100%;
        }
        
        .movie-card-enhanced:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.3);
            border-color: rgba(129, 140, 248, 0.4);
            background: rgba(30, 41, 59, 0.95);
        }
        
        .platform-badge {
            display: inline-block;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            padding: 0.25rem 0.5rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            margin: 0.1rem;
        }
        
        .rating-badge {
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white;
            padding: 0.25rem 0.5rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        
        .match-badge {
            background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
            color: white;
            padding: 0.25rem 0.5rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        
        .stButton>button {
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 0.75rem 1.5rem !important;
            font-weight: 600 !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3) !important;
        }
        
        .stButton>button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 25px rgba(99, 102, 241, 0.4) !important;
        }
        
        .sidebar-card {
            background: rgba(30, 41, 59, 0.6);
            border-radius: 12px;
            padding: 1rem;
            margin: 0.5rem 0;
            border: 1px solid rgba(99, 102, 241, 0.1);
        }
        
        .trending-card {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(220, 38, 38, 0.2) 100%);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 8px;
            padding: 0.75rem;
            margin: 0.25rem 0;
        }
        
        .ai-explanation {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.2) 100%);
            border-left: 4px solid #6366f1;
            border-radius: 0 12px 12px 0;
            padding: 1.5rem;
            margin: 1rem 0;
            font-size: 1.1rem;
            line-height: 1.6;
            color: #e2e8f0;
        }
        
        .stats-container {
            display: flex;
            justify-content: space-around;
            background: rgba(30, 41, 59, 0.8);
            border-radius: 12px;
            padding: 1rem;
            margin: 1rem 0;
        }
        
        .stat-item {
            text-align: center;
        }
        
        .stat-number {
            font-size: 1.5rem;
            font-weight: 700;
            color: #6366f1;
        }
        
        .stat-label {
            font-size: 0.9rem;
            color: #94a3b8;
        }
        </style>
        """, unsafe_allow_html=True)
    
    def _render_header(self):
        """Render the enhanced header"""
        st.markdown('<h1 class="mirai-header">🤖 MIRAI AI</h1>', unsafe_allow_html=True)
        st.markdown('<p class="mirai-subtitle">Revolutionary AI-Powered Movie & TV Discovery Engine</p>', unsafe_allow_html=True)
        
        # Stats bar
        self._render_stats_bar()
    
    def _render_stats_bar(self):
        """Render statistics bar"""
        try:
            # Get stats from backend
            response = requests.get(f"{self.api_base_url}/stats")
            if response.status_code == 200:
                stats = response.json()
                
                st.markdown(f"""
                <div class="stats-container">
                    <div class="stat-item">
                        <div class="stat-number">{stats.get('total_titles', '10K+')}</div>
                        <div class="stat-label">Movies & Shows</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{stats.get('languages', '15+')}</div>
                        <div class="stat-label">Languages</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{stats.get('platforms', '50+')}</div>
                        <div class="stat-label">Platforms</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{stats.get('ai_explanations', '∞')}</div>
                        <div class="stat-label">AI Explanations</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        except:
            # Fallback stats
            st.markdown("""
            <div class="stats-container">
                <div class="stat-item">
                    <div class="stat-number">10K+</div>
                    <div class="stat-label">Movies & Shows</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">15+</div>
                    <div class="stat-label">Languages</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">50+</div>
                    <div class="stat-label">Platforms</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">∞</div>
                    <div class="stat-label">AI Explanations</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    def _render_enhanced_sidebar(self):
        """Render enhanced sidebar with advanced features"""
        st.sidebar.markdown("### 👤 User Profile")
        
        # User ID and profile
        self.user_id = st.sidebar.text_input("User ID", value=self.user_id, help="Your unique identifier for personalized recommendations")
        
        # Language preference
        languages = ["Auto-detect", "English", "हिंदी (Hindi)", "తెలుగు (Telugu)", "தமிழ் (Tamil)", "Español", "Français", "Deutsch", "中文", "日本語"]
        language_pref = st.sidebar.selectbox("Preferred Language", languages, help="AI will respond in your preferred language")
        
        st.sidebar.divider()
        
        # Advanced Filters
        st.sidebar.markdown("### 🎛️ Advanced Filters")
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            media_type = st.selectbox("Media Type", ["All", "Movies", "TV Shows", "Documentaries", "Anime"])
            min_rating = st.slider("Min Rating", 0.0, 10.0, 6.0, 0.5)
            
        with col2:
            year_range = st.slider("Year Range", 1970, 2025, (1990, 2025))
            max_runtime = st.slider("Max Runtime (min)", 30, 300, 180, 10)
        
        # Genre selection with multi-select
        all_genres = ["Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary", "Drama", 
                     "Family", "Fantasy", "History", "Horror", "Music", "Mystery", "Romance", 
                     "Science Fiction", "TV Movie", "Thriller", "War", "Western", "Anime", "Bollywood"]
        
        selected_genres = st.sidebar.multiselect("Genres (optional)", all_genres, 
                                               default=[], help="Select multiple genres")
        
        # Streaming platforms
        platforms = ["Netflix", "Prime Video", "Disney+", "HBO Max", "Hulu", "Apple TV+", "Paramount+", 
                    "Peacock", "Crunchyroll", "Hotstar", "Zee5", "SonyLIV"]
        selected_platforms = st.sidebar.multiselect("Available on", platforms, 
                                                   default=[], help="Filter by streaming platforms")
        
        st.sidebar.divider()
        
        # AI Settings
        st.sidebar.markdown("### 🤖 AI Settings")
        
        explanation_style = st.sidebar.selectbox("Explanation Style", 
                                             ["Detailed Analysis", "Quick Summary", "Technical", "Casual"],
                                             help="How detailed should AI explanations be?")
        
        diversity_level = st.sidebar.slider("Diversity Level", 0.0, 1.0, 0.7, 0.1,
                                           help="How diverse should recommendations be?")
        
        include_trending = st.sidebar.checkbox("Include Trending", value=True,
                                             help="Include currently popular content")
        
        st.sidebar.divider()
        
        # Store filter state BEFORE actions
        self.filters = {
            'media_type': media_type,
            'min_rating': min_rating,
            'year_range': year_range,
            'max_runtime': max_runtime,
            'genres': selected_genres,
            'platforms': selected_platforms,
            'explanation_style': explanation_style,
            'diversity_level': diversity_level,
            'include_trending': include_trending,
            'language_pref': language_pref
        }
        
        # Quick Actions
        st.sidebar.markdown("### ⚡ Quick Actions")
        
        if st.sidebar.button("🎲 Surprise Me!", use_container_width=True):
            self._get_surprise_recommendations()
        
        if st.sidebar.button("🔥 Trending Now", use_container_width=True):
            self._get_trending_recommendations()
        
        if st.sidebar.button("📚 My Watchlist", use_container_width=True):
            self._show_watchlist()
        
        if st.sidebar.button("📊 My Stats", use_container_width=True):
            self._show_user_stats()
    
    def _render_main_content(self):
        """Render main content area"""
        # Search section
        st.markdown("### 🔍 What are you in the mood for?")
        st.markdown("<div style='margin-bottom: 10px;'>Describe your mood, preferences, or what you want to watch:</div>", unsafe_allow_html=True)
        
        # Query input with suggestions
        query_col1, query_col2 = st.columns([5, 1])
        
        with query_col1:
            query = st.text_input(
                "Search query",
                label_visibility="collapsed",
                placeholder="e.g., 'I want a mind-bending sci-fi thriller with amazing visuals' or 'कोई अच्छी हिंदी कॉमेडी फिल्म सुझाएं'",
                help="You can search in any language! MIRAI AI will understand and translate."
            )
        
        with query_col2:
            search_clicked = st.button("🚀 Search", type="primary", use_container_width=True)
        
        # Quick query suggestions
        st.markdown("#### 💡 Try these searches:")
        
        sample_queries = [
            "Mind-bending movies that make you think",
            "Feel-good comedies for a rainy day",
            "Intense crime thrillers with plot twists",
            "Beautiful animated films for adults",
            "Inspiring true stories",
            "कोई रोमांचक हिंदी फिल्म",
            "తెలుగులో మంచి కామెడీ సినిమాలు",
            "Visually stunning sci-fi epics"
        ]
        
        cols = st.columns(4)
        for i, sample_query in enumerate(sample_queries[:8]):
            with cols[i % 4]:
                if st.button(f"🎬 {sample_query[:25]}...", key=f"sample_{i}", help=sample_query):
                    self._get_sample_recommendations(sample_query)
        
        # Main search results
        if search_clicked and query.strip():
            self._get_ai_recommendations(query)
        
        # Default trending content
        elif not search_clicked:
            self._render_trending_section()
    
    def _get_ai_recommendations(self, query: str):
        """Get AI-powered recommendations"""
        with st.spinner("🤖 MIRAI AI is analyzing your preferences and searching through 10,000+ titles..."):
            try:
                payload = {
                    "query": query,
                    "user_id": self.user_id,
                    **self.filters
                }
                
                response = requests.post(f"{self.api_base_url}/recommend", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    self._render_recommendation_results(data, query)
                else:
                    st.error(f"AI Error: {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("❌ Could not connect to MIRAI AI backend. Please ensure the server is running.")
                st.info("💡 Run: `cd backend && uvicorn main:app --port 8000` to start the AI engine")
    
    def _render_recommendation_results(self, data: Dict, original_query: str):
        """Render recommendation results with enhanced UI"""
        
        # AI Analysis Section
        st.markdown("### 🤖 MIRAI AI Analysis")
        
        with st.container():
            if data.get("translated_query"):
                st.info(f"🌐 **Translated Query:** *{data['translated_query']}*")
            
            if data.get("explanation"):
                st.markdown(f'<div class="ai-explanation">{data["explanation"]}</div>', unsafe_allow_html=True)
        
        # Stats and insights
        if "total_candidates" in data:
            st.caption(f"📊 Analyzed {data['total_candidates']} titles to find these perfect matches")
        
        st.divider()
        
        # Recommendations Grid
        st.markdown("### 🎬 Your Personalized Recommendations")
        
        if "movies" in data and data["movies"]:
            movies = data["movies"]
            
            # Create responsive grid
            cols = st.columns(3)
            
            for idx, movie in enumerate(movies):
                with cols[idx % 3]:
                    self._render_enhanced_movie_card(movie, idx)
        else:
            st.warning("🤔 No matches found. Try adjusting your filters or changing your query!")
    
    def _render_enhanced_movie_card(self, movie: Dict, index: int):
        """Render enhanced movie card with interactive features"""
        
        # Get movie details
        title = movie.get('title', 'Unknown Title')
        year = str(movie.get('release_date', ''))[:4]
        rating = movie.get('rating', 0)
        match_score = movie.get('match_score', 0)
        overview = movie.get('overview', 'No description available')
        poster_url = movie.get('poster_path') or "https://via.placeholder.com/500x750/1e293b/94a3b8?text=No+Poster"
        providers = movie.get('providers', [])
        media_type = movie.get('media_type', 'movie')
        
        # Create enhanced card
        card_html = f"""
        <div class="movie-card-enhanced">
            <div style="display: flex; gap: 1rem;">
                <div style="flex-shrink: 0;">
                    <img src="{poster_url}" style="width: 120px; height: 180px; object-fit: cover; border-radius: 8px;" alt="{title}">
                </div>
                <div style="flex-grow: 1;">
                    <h4 style="margin: 0 0 0.5rem 0; color: #f8fafc;">{title} {f'({year})' if year else ''}</h4>
                    <div style="display: flex; gap: 0.5rem; margin-bottom: 0.5rem; flex-wrap: wrap;">
                        <span class="match-badge">🎯 {match_score}% Match</span>
                        <span class="rating-badge">⭐ {rating:.1f}/10</span>
                        <span style="background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 0.25rem 0.5rem; border-radius: 20px; font-size: 0.8rem;">{media_type.title()}</span>
                    </div>
                    <p style="font-size: 0.9rem; color: #cbd5e1; margin: 0.5rem 0; line-height: 1.4;">{overview[:200]}{'...' if len(overview) > 200 else ''}</p>
                    {''.join([f'<span class="platform-badge">{provider}</span>' for provider in providers[:3]])}
                    {f'<span style="color: #94a3b8; font-size: 0.8rem;">+{len(providers)-3} more</span>' if len(providers) > 3 else ''}
                </div>
            </div>
        </div>
        """
        
        st.markdown(card_html, unsafe_allow_html=True)
        
        # Interactive buttons
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        
        with btn_col1:
            if st.button("🔥 Love it", key=f"like_{index}_{movie['id']}", use_container_width=True):
                self._rate_movie(movie['id'], "like")
                st.toast(f"❤️ Added '{title}' to your liked titles!", icon="🔥")
        
        with btn_col2:
            if st.button("👎 Pass", key=f"dislike_{index}_{movie['id']}", use_container_width=True):
                self._rate_movie(movie['id'], "dislike")
                st.toast(f"👎 We'll show you fewer titles like '{title}'", icon="👎")
        
        with btn_col3:
            if st.button("📋 Watchlist", key=f"watchlist_{index}_{movie['id']}", use_container_width=True):
                self._add_to_watchlist(movie)
                st.toast(f"📋 Added '{title}' to your watchlist!", icon="📋")
    
    def _rate_movie(self, tmdb_id: int, interaction_type: str):
        """Rate a movie — uses /api/interact endpoint"""
        try:
            response = requests.post(
                f"{self.api_base_url}/interact",
                json={"user_id": self.user_id, "tmdb_id": tmdb_id, "interaction_type": interaction_type},
                timeout=5,
            )
            if response.status_code == 200:
                return True
        except Exception:
            pass
        return False
    
    def _add_to_watchlist(self, movie: Dict):
        """Add movie to watchlist"""
        if movie not in self.watchlist:
            self.watchlist.append(movie)
            # Store in session state
            if 'watchlist' not in st.session_state:
                st.session_state.watchlist = []
            st.session_state.watchlist.append(movie)
    
    def _get_sample_recommendations(self, query: str):
        """Get sample recommendations for demo queries"""
        # This would make an API call with the sample query
        st.info(f"🎬 Getting recommendations for: '{query}'")
        self._get_ai_recommendations(query)
    
    def _get_surprise_recommendations(self):
        """Get surprise recommendations"""
        surprise_queries = [
            "Something completely different from what I usually watch",
            "A hidden gem that most people haven't heard of",
            "The most unique and unconventional story ever told",
            "Something that will challenge my perspective",
            "A movie that broke all the rules and succeeded"
        ]
        
        import random
        random_query = random.choice(surprise_queries)
        self._get_ai_recommendations(random_query)
    
    def _get_trending_recommendations(self):
        """Get trending recommendations"""
        self._get_ai_recommendations("What's trending and popular right now")
    
    def _show_watchlist(self):
        """Show user's watchlist"""
        st.markdown("### 📋 Your Watchlist")
        
        watchlist = st.session_state.get('watchlist', [])
        
        if watchlist:
            for movie in watchlist:
                self._render_enhanced_movie_card(movie, watchlist.index(movie))
        else:
            st.info("Your watchlist is empty. Start adding movies you want to watch later!")
    
    def _show_user_stats(self):
        """Show user statistics"""
        st.markdown("### 📊 Your Viewing Stats")
        
        try:
            response = requests.get(f"{self.api_base_url}/user_stats/{self.user_id}")
            if response.status_code == 200:
                stats = response.json()
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Movies Liked", stats.get('movies_liked', 0))
                with col2:
                    st.metric("TV Shows Liked", stats.get('tv_shows_liked', 0))
                with col3:
                    st.metric("Watchlist Size", stats.get('watchlist_size', 0))
                with col4:
                    st.metric("Searches Made", stats.get('searches_made', 0))
                
                # Genre preferences
                if 'genre_preferences' in stats:
                    st.markdown("#### 🎭 Your Genre Preferences")
                    genres = stats['genre_preferences']
                    if genres:
                        # Create a simple bar chart
                        genre_df = pd.DataFrame(list(genres.items()), columns=['Genre', 'Count'])
                        st.bar_chart(genre_df.set_index('Genre'))
                
            else:
                st.info("Start using MIRAI to see your personalized stats!")
        except:
            st.info("Stats will appear here once you start using the app!")
    
    def _render_trending_section(self):
        """Render trending content section"""
        st.markdown("### 🔥 Trending Now")
        
        try:
            response = requests.get(f"{self.api_base_url}/trending")
            if response.status_code == 200:
                trending_data = response.json()
                
                if "trending" in trending_data:
                    trending = trending_data["trending"]
                    
                    cols = st.columns(4)
                    for idx, item in enumerate(trending[:8]):
                        with cols[idx % 4]:
                            self._render_trending_card(item)
                
                if "explanation" in trending_data:
                    st.markdown(f'<div class="ai-explanation">{trending_data["explanation"]}</div>', unsafe_allow_html=True)
                    
        except:
            # Fallback trending content
            st.info("🔥 Trending content will appear here!")
    
    def _render_trending_card(self, item: Dict):
        """Render trending item card"""
        title = item.get('title', 'Unknown')
        poster = item.get('poster_path', '')
        reason = item.get('trending_reason', 'Popular')
        
        trending_html = f"""
        <div class="trending-card">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 1.2rem;">🔥</span>
                <div>
                    <div style="font-weight: 600; color: #f8fafc;">{title}</div>
                    <div style="font-size: 0.8rem; color: #94a3b8;">{reason}</div>
                </div>
            </div>
        </div>
        """
        
        st.markdown(trending_html, unsafe_allow_html=True)

def main():
    """Main function to run the enhanced app"""
    app = EnhancedMovieApp()
    app.render_enhanced_ui()

if __name__ == "__main__":
    main()