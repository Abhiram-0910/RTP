# 🎬 MIRAI: Enterprise Hybrid Recommendation Engine

MIRAI is an advanced, production-grade recommendation engine that goes beyond simple keyword matching to solve streaming information overload. It utilizes a Hybrid Recommendation Architecture combining high-dimensional semantic vector search, collaborative filtering, real-time machine learning, and multi-modal generative AI to provide a uniquely powerful cinematic discovery experience.

## 🚀 Enterprise Features (V2 Architecture)

* **Blazing Fast RAG:** Sub-second UI response times achieved by decoupling Gemini LLM generation into asynchronous FastAPI background tasks. The UI paints instantly while explanations stream in.
* **Massive Vector Universe:** Fully indexed database of **18,000+ titles** producing over **28,000+ semantic chunks** in a localized FAISS vector store and PostgreSQL database.
* **Multi-Modal Visual Search:** Powered by Gemini 1.5 Flash, users can upload images (e.g., a rainy cyberpunk street) to automatically extract mood, aesthetic, and genre intent into actionable search queries.
* **Item-to-Item Similarity Search:** Real-time mathematical "nearest neighbor" lookups powering a dynamic "Because you watched" engine.
* **Cinematic DNA Profiling:** A custom algorithm that tracks explicit user interactions to build and visualize a personalized Taste Profile (Decades, Genres, Languages).
* **Smart Progress Tracking:** Fully reactive "Continue Watching" queues driven by native DOM event dispatchers and backend database persistence.
* **High-Concurrency Ingestion:** Custom `asyncio` data pipelines capable of fetching and deduplicating 10,000+ TMDB API records in under 3 minutes.

## 🏗️ Architecture

```text
User → React UI (frontend-react/) → FastAPI (enhanced_main.py)
  ↓                                        ↓
Home.jsx                    ┌──────────────────────────┐
SearchBar.jsx               │   HybridEngine           │
MediaCard.jsx               │   rag_engine.py          │
StatsBar.jsx                │   advanced_recommendation│
                            │   rag_chain.py (LangChain)│
                            └──────┬───────────┬────────┘
                                   ↓           ↓
                            pgvector DB    Gemini 1.5 Flash
                            (PostgreSQL)   ai_explainer.py
                                   ↓
                            FAISS Fallback
                            faiss_fallback.py
                                   ↓
                            TMDB API + JustWatch API


🛠️ Tech Stack
Backend: Python 3.10, FastAPI, SQLAlchemy, Uvicorn, Celery, Redis

AI & Search: LangChain, FAISS, Google Gemini (Pro & Flash 1.5), sentence-transformers

Frontend: React, Vite, TailwindCSS, Framer Motion, Lucide Icons

Database: PostgreSQL (with pgvector support) / SQLite fallback

Deployment: Docker Compose

⚡ Setup & Deployment
Please refer to the detailed instructions in STARTUP_GUIDE.md to set up PostgreSQL with pgvector, configure your API keys, and launch the application.

Quick Start (Docker):
Ensure Docker is installed and your .env is populated with TMDB_API_KEY and GEMINI_API_KEY. 

docker-compose up --build
Access the frontend application at http://localhost:5173 and the backend API at http://localhost:8000.