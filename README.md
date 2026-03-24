# Movies and TV shows Recommendation Engine — AI-Powered Movie & TV Show Recommendation Engine

Movies and TV shows Recommendation Engine is an advanced, production-grade recommendation engine that goes beyond simple keyword matching. It utilizes a hybrid approach, combining semantic vector search, collaborative filtering, and generative AI explanations to provide a uniquely powerful cinematic discovery experience.

## Architecture

```text
User → React UI (frontend-react/) → FastAPI (enhanced_main.py)
  ↓                                        ↓
Home.jsx                    ┌──────────────────────────┐
SearchBar.jsx               │    HybridEngine           │
MediaCard.jsx               │  rag_engine.py            │
StatsBar.jsx                │  advanced_recommendation  │
                            │  rag_chain.py (LangChain) │
                            └──────┬───────────┬────────┘
                                   ↓           ↓
                            pgvector DB    Gemini 1.5 Flash
                            (PostgreSQL)   ai_explainer.py
                                   ↓
                            FAISS Fallback
                            faiss_fallback.py
                                   ↓
                            TMDB API + JustWatch API
```

## Feature Status

| Feature | Status |
| :--- | :--- |
| Semantic search (pgvector + FAISS fallback) | ✅ |
| multilingual-MiniLM embeddings | ✅ |
| Gemini embeddings (secondary/primary configurable) | ✅ |
| RAG explanations (per-movie, structured JSON) | ✅ |
| LangChain RetrievalQA chain (deep analysis) | ✅ |
| Hybrid scoring (semantic + CF + popularity) | ✅ |
| MMR diversity reranking | ✅ |
| Hindi/Telugu multilingual queries | ✅ |
| Hindi/Telugu content in DB (regional TMDB sweep) | ✅ |
| TMDB Watch Providers integration | ✅ |
| JustWatch API integration (enrichment) | ✅ |
| Platform normalization | ✅ |
| React frontend (dark cinematic UI) | ✅ |
| Mobile responsive | ✅ |
| Redis caching + cachetools fallback | ✅ |
| 4 uvicorn workers (50-user concurrency) | ✅ |
| Metrics dashboard (/api/metrics) | ✅ |
| User satisfaction feedback | ✅ |
| **Response time:** warm path <3s, cold path with Gemini may reach 4-6s (Gemini decoupled to background task) | ⚠️ |
| **10,000 titles:** requires full ingestion run (~30-45 min) | ⚠️ |

## Setup & Deployment

Please refer to the detailed instructions in [STARTUP_GUIDE.md](./STARTUP_GUIDE.md) to set up PostgreSQL with pgvector, configure your API keys, ingest data, and launch both the FastAPI backend and the React frontend.
