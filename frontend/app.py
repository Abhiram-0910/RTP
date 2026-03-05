import streamlit as st
import requests

st.set_page_config(page_title="Movie Discovery Engine", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    /* Global Font & Background */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Main Background gradient */
    .stApp {
        background: radial-gradient(circle at top, #0f172a 0%, #020617 100%);
        color: #f8fafc;
    }

    /* Headings */
    h1 {
        font-weight: 700 !important;
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem !important;
        text-align: center;
        font-size: 3.5rem !important;
    }
    
    .subtitle {
        text-align: center;
        color: #94a3b8;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }

    /* Input Field */
    .stTextInput>div>div>input {
        background-color: rgba(30, 41, 59, 0.7) !important;
        color: white !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        font-size: 1.1rem !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06) !important;
        transition: all 0.3s ease !important;
    }
    .stTextInput>div>div>input:focus {
        border-color: #38bdf8 !important;
        box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2) !important;
    }

    /* Primary Search Button */
    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.75rem 2rem !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        letter-spacing: 0.5px;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
        width: 100%;
        margin-top: 10px;
        box-shadow: 0 10px 15px -3px rgba(79, 70, 229, 0.3) !important;
    }
    .stButton>button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 20px 25px -5px rgba(79, 70, 229, 0.4) !important;
    }

    /* Custom Movie Cards */
    .movie-card {
        position: relative;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 10px 20px rgba(0,0,0,0.3);
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s ease;
        background: #1e293b;
        margin-bottom: 1rem;
        aspect-ratio: 2 / 3;
    }
    .movie-card:hover {
        transform: scale(1.03);
        box-shadow: 0 20px 30px rgba(0,0,0,0.5), 0 0 20px rgba(56, 189, 248, 0.2);
    }
    .movie-poster {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }
    .movie-overlay {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        padding: 2rem 1.5rem 1.5rem 1.5rem;
        background: linear-gradient(to top, rgba(2,6,23,0.95) 0%, rgba(2,6,23,0.8) 40%, transparent 100%);
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
    }
    .movie-title {
        color: white;
        font-size: 1.25rem;
        font-weight: 700;
        margin: 0 0 0.5rem 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.5);
    }
    .movie-stats {
        display: flex;
        gap: 0.75rem;
        align-items: center;
        flex-wrap: wrap;
    }
    .badge {
        padding: 0.25rem 0.5rem;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        backdrop-filter: blur(4px);
    }
    .badge-match {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-rating {
        background: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .badge-provider {
        background: rgba(56, 189, 248, 0.2);
        color: #7dd3fc;
        border: 1px solid rgba(56, 189, 248, 0.3);
    }

    /* AI container */
    .ai-box {
        background: linear-gradient(145deg, rgba(30, 58, 138, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%);
        border-left: 4px solid #38bdf8;
        padding: 1.5rem;
        border-radius: 0 12px 12px 0;
        margin: 1.5rem 0 2.5rem 0;
        font-size: 1.1rem;
        line-height: 1.6;
        color: #e2e8f0;
        box-shadow: 0 8px 15px -3px rgba(0, 0, 0, 0.2);
    }
    
    /* Subheaders */
    h2, h3 {
        color: #f8fafc !important;
        font-weight: 600 !important;
    }
    
</style>
""", unsafe_allow_html=True)

st.title("MIRAI ENGINE")
st.markdown("<p class='subtitle'>The Next Generation of AI Movie & TV Show Discovery.</p>", unsafe_allow_html=True)

# Sidebar with info and filters
with st.sidebar:
    st.header("👤 User Tools")
    user_id = st.text_input("User ID (for recommendations):", value="demo_user")
    
    st.header("🎛️ Filters")
    media_type = st.selectbox("Media Type", ["All", "Movies", "TV Shows"])
    min_rating = st.slider("Minimum Rating", 0.0, 10.0, 5.0, 0.5)
    
    # Simple predefined genres for demonstration (in a real app, query distinct genres from DB)
    genre = st.selectbox("Genre (optional)", ["Any", "Action", "Comedy", "Drama", "Sci-Fi", "Horror", "Romance", "Thriller"])
    genre_query = None if genre == "Any" else genre
    
    st.divider()

    st.header("ℹ️ About")
    st.write("This recommendation system uses:")
    st.write("- 🧠 **paraphrase-multilingual-MiniLM-L12-v2**")
    st.write("- 🔍 **FAISS** + **PostgreSQL**")
    st.write("- 🤝 **Hybrid Filtering**")
    
    st.divider()
    st.write("**Match Score**: AI Similarity + Rating Boost")

query = st.text_input(
    "Describe your mood or what you want to watch (supports Hindi, Telugu, etc!):", 
    placeholder="e.g., A dark thriller with a mind-bending twist set in space"
)

if st.button("🔍 Find Movies", type="primary"):
    if query.strip():
        with st.spinner("🎭 Analyzing your preferences with AI..."):
            try:
                payload = {
                    "query": query,
                    "user_id": user_id,
                    "genre": genre_query,
                    "min_rating": min_rating,
                    "media_type": media_type
                }
                
                response = requests.post(
                    "http://127.0.0.1:8000/api/recommend", 
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "movies" in data and data["movies"]:
                        # AI Analysis Section
                        st.subheader("🤖 AI Analysis")
                        
                        if data.get("translated_query"):
                            st.info(f"🌐 Extracted and translated query: *{data['translated_query']}*")
                            
                        explanation = data.get("explanation", "")
                        
                        # Display explanation with custom styling
                        with st.container():
                            st.markdown(
                                f"<div class='ai-box'>"
                                f"<strong>🤖 MIRAI Analysis:</strong><br><br>"
                                f"{explanation.replace(chr(10), '<br>').replace('🤖 **MIRAI AI Says:**<br><br>', '')}"
                                f"</div>", 
                                unsafe_allow_html=True
                            )
                        
                        # Stats
                        if "total_candidates" in data:
                            st.caption(f"📊 Scored {data['total_candidates']} movies to find these recommendations")
                        
                        st.divider()
                        
                        # Recommendations Section
                        st.subheader("🎬 Top Recommendations")
                        
                        cols = st.columns(3)
                        for idx, movie in enumerate(data["movies"]):
                            with cols[idx % 3]:
                                # Card container
                                with st.container():
                                    poster_url = movie.get('poster_path') or "https://via.placeholder.com/500x750/1e293b/94a3b8?text=No+Poster"
                                    year = str(movie.get('release_date', ''))[:4]
                                    year_str = f" ({year})" if year else ""
                                    
                                    # Providers HTML
                                    providers = movie.get('providers', [])
                                    provider_html = ""
                                    if providers:
                                        provider_html = f"<span class='badge badge-provider'>📺 {providers[0]}"
                                        if len(providers) > 1:
                                            provider_html += f" +{len(providers)-1}"
                                        provider_html += "</span>"

                                    # HTML Card
                                    card_html = f"""
                                    <div class="movie-card">
                                        <img src="{poster_url}" class="movie-poster" alt="{movie['title']}">
                                        <div class="movie-overlay">
                                            <h3 class="movie-title">{movie['title']}{year_str}</h3>
                                            <div class="movie-stats">
                                                <span class="badge badge-match">🎯 {movie.get('match_score', 0)}% Match</span>
                                                <span class="badge badge-rating">⭐ {movie['rating']}/10</span>
                                                {provider_html}
                                            </div>
                                        </div>
                                    </div>
                                    """
                                    st.markdown(card_html, unsafe_allow_html=True)
                                    
                                    # Synopsis expander below the card
                                    with st.expander("📖 Synopsis"):
                                        st.write(movie['overview'])
                                    
                                    # Interaction Buttons
                                    btn_cols = st.columns(2)
                                    with btn_cols[0]:
                                        if st.button("🔥 Love it", key=f"like_{movie['id']}", use_container_width=True):
                                            requests.post(
                                                "http://127.0.0.1:8000/api/rate",
                                                json={"user_id": user_id, "tmdb_id": movie['id'], "interaction_type": "like"}
                                            )
                                            st.toast(f"Loved '{movie['title']}'! We will show you more like this.", icon="🔥")
                                    with btn_cols[1]:
                                        if st.button("👎 Hard Pass", key=f"dislike_{movie['id']}", use_container_width=True):
                                            requests.post(
                                                "http://127.0.0.1:8000/api/rate",
                                                json={"user_id": user_id, "tmdb_id": movie['id'], "interaction_type": "dislike"}
                                            )
                                            st.toast(f"Passed on '{movie['title']}'. We've updated your preferences.", icon="👎")
                                            
                    else:
                        st.warning("No matches found. Try widening your filters or changing your query!")
                else:
                    st.error(f"Backend Error: {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("❌ Could not connect to the backend. Make sure FastAPI is running on port 8000.")
                st.info("💡 Run: `uvicorn main:app --port 8000` in the backend folder")
                
    else:
        st.warning("⚠️ Please enter a query first.")

# Footer
st.divider()
st.caption("Built with ❤️ using FastAPI, Streamlit, FAISS, and Scikit-learn")
