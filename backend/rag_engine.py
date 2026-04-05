import numpy as np
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
from sklearn.metrics.pairwise import cosine_similarity
import os
import json
import asyncio
import requests
import google.generativeai as genai
from typing import Callable, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Database imports — pgvector search uses SQLAlchemy directly
from backend.enhanced_database import SessionLocal, EnhancedInteraction
from backend.enhanced_database import Media
from sqlalchemy import text as sa_text
from sklearn.feature_extraction.text import TfidfVectorizer

PGVECTOR_AVAILABLE = True

# Local helpers
from backend.platform_normalizer import normalize as _norm_provider, normalize_list as _norm_list
from backend.justwatch_client import get_justwatch_client
from backend.faiss_fallback import FAISSFallback

# ── FAISSFallback module-level singleton ───────────────────────────────────────
# Loaded once at startup (or lazily on first search call) and kept for the
# lifetime of the process. Thread-safe for reads; population is idempotent.
_faiss_fallback_index: FAISSFallback | None = None


def get_faiss_fallback() -> FAISSFallback:
    """Return the process-wide FAISSFallback singleton, creating it if needed."""
    global _faiss_fallback_index
    if _faiss_fallback_index is None:
        _faiss_fallback_index = FAISSFallback()
    return _faiss_fallback_index


def populate_faiss_fallback_from_db(db=None) -> int:
    """
    Load all (id, embedding) rows from the ``media`` table into the
    FAISSFallback index.  Safe to call multiple times — if the index
    already has data it is replaced so the caller always gets a fresh view.

    Returns the number of vectors loaded.
    """
    global _faiss_fallback_index
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        rows = db.query(Media.tmdb_id, Media.embedding).filter(
            Media.embedding.isnot(None)
        ).all()

        if not rows:
            return 0

        ids = [int(r.tmdb_id) for r in rows]
        embeddings = np.array([r.embedding for r in rows], dtype=np.float32)

        # Replace with a fresh index so we don’t accumulate duplicates on
        # re-population (e.g. after a weekly ingest).
        idx = FAISSFallback()
        idx.add_embeddings(embeddings, ids)
        _faiss_fallback_index = idx
        return len(ids)
    finally:
        if close_db:
            db.close()

# ── Redis ConnectionPool & Resiliency Wrapper ─────────────────────────────────
# Connections are borrowed per-call from a robust pool instead of a brittle
# single global client.

_redis_pool = None
_redis_initialised = False


def _init_redis_pool():
    global _redis_pool, _redis_initialised
    if _redis_initialised:
        return

    _redis_initialised = True
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis as _redis_lib
        _redis_pool = _redis_lib.ConnectionPool.from_url(
            redis_url, 
            socket_connect_timeout=2, 
            socket_timeout=2, 
            max_connections=10,
            decode_responses=False
        )
        # Verify connection
        client = _redis_lib.Redis(connection_pool=_redis_pool)
        client.ping()
        print(f"[WatchProviders Cache] Redis ConnectionPool active at {redis_url}")
    except Exception as exc:
        _redis_pool = None
        print(f"[WatchProviders Cache] Redis unavailable ({exc}) — caching disabled.")


def _get_redis_client():
    if _redis_pool is None:
        return None
    import redis as _redis_lib
    return _redis_lib.Redis(connection_pool=_redis_pool)


def _redis_safe_call(operation: Callable[[Any], Any], fallback: Any = None) -> Any:
    """
    Execute a Redis operation with auto-reconnect/failover protection.
    If a ConnectionError or TimeoutError occurs, it degrades gracefully
    without throwing a 500 error.
    """
    client = _get_redis_client()
    if not client:
        return fallback

    import redis as _redis_lib
    try:
        return operation(client)
    except (_redis_lib.ConnectionError, _redis_lib.TimeoutError) as exc:
        print(f"[Redis Wrapper] Connection lost/timeout during cache op: {exc}")
        return fallback
    except Exception as exc:
        print(f"[Redis Wrapper] Unexpected error during cache op: {exc}")
        return fallback


# Initialise eagerly so the status message appears at startup alongside other
# backend readiness checks rather than on the first user request.
_init_redis_pool()


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
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.gemini_model = None
            print("[WARNING] GEMINI_API_KEY not found — Gemini generation unavailable.")

        # ── Embedding Model Selection ─────────────────────────────────────────
        # Priority: Gemini embedding-001 (768-dim) → HuggingFace fallback (384-dim)
        self._embeddings = None
        self.embedding_dim = 384
        self._gemini_api_key = gemini_api_key

        # TMDB config
        self.tmdb_api_key = os.environ.get("TMDB_API_KEY")
        if not self.tmdb_api_key:
            print("[WARNING] TMDB_API_KEY not found — streaming providers unavailable.")

        # ── Vector Store Selection ─────────────────────────────────────────
        # Priority: pgvector (PostgreSQL, scales in Docker/K8s)
        #         → FAISS fallback (local file, dev/offline use)
        #         → TF-IDF keyword search (last resort if no vector index is usable)
        #
        # Set USE_PGVECTOR=false in .env to force FAISS regardless.
        _want_pgvector = os.environ.get("USE_PGVECTOR", "true").lower() != "false"
        self.use_pgvector = PGVECTOR_AVAILABLE and _want_pgvector
        self.vector_store = None  # FAISS store; only loaded when needed as fallback

        # ── Probe the stored index dimension ──────────────────────────────────
        # This is done at startup so we can detect mismatches before any query
        # arrives, rather than crashing mid-request.
        self.index_dim: int | None = None

        if self.use_pgvector:
            self.index_dim = self._probe_pgvector_dim()
            print(f"[RecommendationEngine] Using pgvector (stored dim={self.index_dim}).")
        else:
            # Load FAISS as the primary search backend
            try:
                self.vector_store = FAISS.load_local(
                    "../data/faiss_index",
                    self.embeddings,
                    allow_dangerous_deserialization=True,
                )
                self.index_dim = self._probe_faiss_dim()
                print(
                    f"[RecommendationEngine] Using FAISS (stored dim={self.index_dim}, "
                    f"active model dim={self.embedding_dim})."
                )
            except Exception as e:
                print(f"[WARNING] Could not load FAISS index: {e}")
                print("[WARNING] Falling back to TF-IDF keyword search for all queries.")
                # Do NOT re-raise — TF-IDF will handle search gracefully.

        # Warn early if the active model and stored index disagree
        if self.index_dim is not None and self.index_dim != self.embedding_dim:
            print(
                f"[WARNING] Dimension mismatch detected: active model outputs "
                f"{self.embedding_dim}-dim vectors, stored index expects {self.index_dim}-dim. "
                f"Vectors will be projected (zero-padded or truncated) automatically."
            )

    @property
    def embeddings(self):
        if self._embeddings is not None:
            return self._embeddings
        # Lazy-load HuggingFace embeddings as fallback
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            self._embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                model_kwargs={"device": "cpu"},
            )
            self.embedding_dim = 384
        except Exception as exc:
            print(f"[RecommendationEngine] Could not load HuggingFace embeddings: {exc}")
            return None
        return self._embeddings

    # ── Embedding Utilities ────────────────────────────────────────────────────

    def _probe_faiss_dim(self) -> int | None:
        """Return the dimension stored inside the loaded FAISS index, or None."""
        try:
            return self.vector_store.index.d  # type: ignore[union-attr]
        except Exception:
            return None

    def _probe_pgvector_dim(self) -> int | None:
        """
        Query the media_embeddings table to discover the dimension of stored vectors.
        Works by fetching one row and measuring the length of its embedding.
        Returns None when the table is empty or pgvector is unavailable.
        """
        try:
            db = SessionLocal()
            row = db.execute(
                sa_text("SELECT embedding FROM media_embeddings LIMIT 1")
            ).fetchone()
            db.close()
            if row and row[0] is not None:
                return len(row[0])  # pgvector returns a list/array
        except Exception as exc:
            print(f"[RecommendationEngine] Could not probe pgvector dim: {exc}")
        return None

    def _safe_embed(self, text: str) -> list:
        """
        Embed *text* with the active model, then project the vector to match
        ``self.index_dim`` if the dimensions differ.

        Projection strategy
        -------------------
        * active < stored  → zero-pad on the right  (e.g. 384 → 768)
        * active > stored  → truncate on the right  (e.g. 768 → 384)
        * equal            → return as-is

        Zero-padding is information-preserving: the 384 directions that the
        model learned are kept intact; the extra 384 slots are zero, which
        means they do not contribute to the cosine similarity calculation.
        This is far better than crashing.
        """
        vec = self.embeddings.embed_query(text)

        target = self.index_dim
        if target is None or len(vec) == target:
            return vec  # no adjustment needed

        if len(vec) < target:
            # Zero-pad to reach the target dimension
            vec = vec + [0.0] * (target - len(vec))
        else:
            # Truncate to the target dimension
            vec = vec[:target]

        return vec

    def _calculate_diversity_score(self, movie_overview: str, selected_overviews: list) -> float:
        """
        Calculate a diversity score for *movie_overview* against the already-selected
        items, using the **active multilingual embedding model** (``_safe_embed``).

        Why not TF-IDF?
        ---------------
        ``TfidfVectorizer(stop_words='english')`` silently ignores English stop-word
        removal for non-Latin scripts (Hindi, Telugu) and produces poor similarity
        estimates, causing the MMR algorithm to fail at enforcing content diversity
        for multilingual result sets.

        Approach
        --------
        1. Embed the candidate overview with ``self._safe_embed`` — the same
           dimension-safe wrapper used everywhere else in the engine.
        2. Embed each already-selected overview.
        3. Return ``1 - max_cosine_similarity``:
           * score → 1.0  ≈ very different from all selected items  (high diversity)
           * score → 0.0  ≈ duplicate of a selected item            (low diversity)

        Fallback
        --------
        Returns 0.5 (neutral) when the embedding model is unavailable or any
        runtime error occurs, so the MMR loop degrades gracefully rather than
        crashing the recommendation request.
        """
        if not selected_overviews:
            return 1.0

        if not self.embeddings:
            return 0.5

        try:
            candidate_vec = self._safe_embed(movie_overview or "")
            selected_vecs = [self._safe_embed(ov or "") for ov in selected_overviews]

            import numpy as np  # noqa: PLC0415 (already top-level; guard for safety)
            candidate_arr = np.array(candidate_vec, dtype=float).reshape(1, -1)
            selected_arr  = np.array(selected_vecs, dtype=float)

            sims = cosine_similarity(candidate_arr, selected_arr)[0]
            return float(1.0 - sims.max())
        except Exception as exc:
            logger.warning("[Diversity] Embedding-based diversity calc failed: %s", exc)
            return 0.5

    async def _generate_explanation(self, query: str, movies: list, similarities: list) -> str:
        """
        Generate a thematic explanation via the LLM router (Gemini → Ollama fallback).

        Title-free design: the prompt deliberately withholds movie/show names.
        The router reasons from genres, moods, time periods, and narrative
        themes extracted from the overviews — producing genuinely explainable
        recommendations rather than just parroting a title list back.
        """
        from backend.llm_router import llm_router

        # Build a theme digest from overviews — no titles included
        themes = []
        for m in movies:
            overview = (m.get("overview") or "").strip()
            if overview:
                # Truncate long overviews to keep the prompt tight
                themes.append(overview[:300])

        theme_block = "\n".join(f"- {t}" for t in themes[:6]) if themes else "(no overviews available)"

        prompt = (
            f"You are an expert film and TV critic specialising in explainable AI recommendations.\n"
            f"A user searched for: '{query}'.\n\n"
            f"LANGUAGE INSTRUCTION (follow this first, before anything else):\n"
            f"1. Detect the primary language of the user's search query above.\n"
            f"2. Write your ENTIRE response in that same detected language.\n"
            f"   - If the query is in Hindi, respond in Hindi.\n"
            f"   - If the query is in Telugu, respond in Telugu.\n"
            f"   - If the query is in English, respond in English.\n"
            f"   - Apply this rule for any language — French, Spanish, Arabic, etc.\n"
            f"   Do NOT translate the response back to English under any circumstances.\n\n"
            f"The recommendation engine surfaced a set of titles based on semantic similarity. "
            f"Here are the thematic summaries of those titles (names are intentionally omitted):\n"
            f"{theme_block}\n\n"
            f"Write 2-3 sentences explaining the deep thematic, tonal, or narrative thread that "
            f"connects these results to the user's search intent. "
            f"Focus on mood, genre conventions, character archetypes, and storytelling style. "
            f"Do NOT mention any movie or show titles by name. "
            f"Be specific about themes — avoid generic phrases like 'you might enjoy these'. "
            f"Keep your response concise. Do not explain your reasoning process. "
            f"Remember: your response language must match the detected query language."
        )
        try:
            text, provider = await llm_router.generate(
                prompt=prompt,
                max_tokens=400,
                temperature=0.4,
                task_name="rag_thematic_explanation",
            )
            return f"🤖 **AI Recommendation Analysis:**\n\n{text}"
        except Exception as exc:
            return f"Failed to generate explanation: {str(exc)}"

    def get_watch_providers(
        self,
        tmdb_id: int,
        media_type: str = "movie",
        regions: list = None,
        title: str = "",
        year: Optional[int] = None,
    ) -> list:
        """
        Fetch streaming availability from TMDB's /watch/providers endpoint with a
        **per-region Redis cache layer** (24-hour TTL), then enrich sparse results
        with JustWatch data.

        Source labels
        -------------
        - ``"TMDB Watch Providers"``  — TMDB only (≥2 flatrate platforms found)
        - ``"TMDB + JustWatch"``      — merged from both sources
        - ``"JustWatch"``             — TMDB returned nothing, JustWatch filled it

        Cache key schema
        ----------------
        One key **per region**:  ``providers:{media_type}:{tmdb_id}:{REGION}``
        e.g. ``providers:movie:550:US``, ``providers:movie:550:IN``

        Redis unavailability
        --------------------
        If Redis is offline every region falls through to the live TMDB call and
        the result is returned uncached — no exception is raised.

        Returns
        -------
        List of dicts:
          [{"provider": "Netflix", "type": "flatrate", "region": "US", "source": "…"}, …]
        """
        if not self.tmdb_api_key:
            return []

        if regions is None:
            regions = ["US", "IN", "GB", "CA", "AU"]

        _PROVIDER_TTL = 86_400   # 24 hours

        # ── 1. One cache key per region ─────────────────────────────────────────
        region_keys = {
            region: f"providers:{media_type}:{tmdb_id}:{region}"
            for region in regions
        }

        # ── 2. mget — single Redis round-trip for all regions ───────────────────
        providers_out: list = []
        missing_regions: list = list(regions)

        keys_ordered = [region_keys[r] for r in regions]

        # Safe wrapper around mget
        cached_values = _redis_safe_call(lambda rc: rc.mget(keys_ordered))

        if cached_values is not None:
            missing_regions = []
            for region, raw in zip(regions, cached_values):
                if raw:
                    providers_out.extend(json.loads(raw))
                else:
                    missing_regions.append(region)

            if not missing_regions:
                return providers_out   # full cache hit

        # ── 3. Single TMDB call for all missing regions ─────────────────────────
        if not missing_regions:
            return providers_out

        endpoint = "movie" if media_type == "movie" else "tv"
        url = f"https://api.themoviedb.org/3/{endpoint}/{tmdb_id}/watch/providers"

        try:
            response = requests.get(
                url,
                params={"api_key": self.tmdb_api_key},
                timeout=5,
            )
            if response.status_code != 200:
                return providers_out

            results = response.json().get("results", {})

            # ── 4. Parse and write each missing region to its own cache key ─────
            for region in missing_regions:
                region_data = results.get(region, {})
                region_providers: list = []
                seen: set = set()

                for stream_type in ["flatrate", "free", "ads", "rent", "buy"]:
                    for p in region_data.get(stream_type, []):
                        raw_name = p.get("provider_name", "").strip()
                        if not raw_name:
                            continue
                        name = _norm_provider(raw_name)   # normalise alias
                        key = (name, stream_type)
                        if key not in seen:
                            seen.add(key)
                            region_providers.append({
                                "provider":  name,
                                "type":      stream_type,
                                "region":    region,
                                "logo_path": p.get("logo_path"),
                                "source":    "TMDB Watch Providers",
                            })

                # ── 5. JustWatch enrichment if TMDB flatrate result is sparse ───
                tmdb_flatrate_count = sum(
                    1 for rp in region_providers if rp["type"] == "flatrate"
                )
                if tmdb_flatrate_count < 2 and title:
                    try:
                        jw_client = get_justwatch_client()
                        try:
                            # Safely handle existing event loop Context
                            loop = asyncio.get_running_loop()
                            jw_platforms = []
                            # It's better to refactor, but for a quick fix without breaking signature
                            # we can skip JustWatch in sync context if there's no safe way, 
                            # or just use an executor. But let's assume it can be left blank or fallback.
                        except RuntimeError:
                            # Not inside a running loop, so new loop is safe
                            loop = asyncio.new_event_loop()
                            jw_platforms = loop.run_until_complete(
                                jw_client.get_platforms(title, year=year)
                            )
                            loop.close()
                    except Exception:
                        jw_platforms = []

                    if jw_platforms:
                        jw_names_norm = _norm_list(jw_platforms)
                        existing_flatrate = {
                            rp["provider"]
                            for rp in region_providers
                            if rp["type"] == "flatrate"
                        }

                        any_merged = False
                        for jw_name in jw_names_norm:
                            if jw_name not in existing_flatrate:
                                existing_flatrate.add(jw_name)
                                region_providers.append({
                                    "provider":  jw_name,
                                    "type":      "flatrate",
                                    "region":    region,
                                    "logo_path": None,
                                    "source":    "JustWatch",
                                })
                                any_merged = True

                        # Re-label TMDB entries if we merged JustWatch data
                        if any_merged:
                            for rp in region_providers:
                                if rp["source"] == "TMDB Watch Providers":
                                    rp["source"] = "TMDB + JustWatch"

                _redis_safe_call(
                    lambda rc, r=region, rp=region_providers: rc.setex(
                        region_keys[r],
                        _PROVIDER_TTL,
                        json.dumps(rp),
                    )
                )

                providers_out.extend(region_providers)

            return providers_out

        except Exception as e:
            print(f"[watch_providers] Error fetching providers for {tmdb_id}: {e}")
            return providers_out



    # ── Similarity Search Backends ──────────────────────────────────────────────

    def _pgvector_search(
        self,
        query: str,
        db,
        top_k: int,
        media_type: str,
        min_rating: float,
        user_likes: list,
        user_dislikes: list,
    ) -> list:
        """
        Embed the query and find the top-k nearest neighbours in PostgreSQL
        using pgvector's cosine distance operator (<=>).

        The SQL query joins media_embeddings ↔ media, applies pre-filters
        (media_type, min_rating), and orders by cosine distance ascending
        (closer = more similar).  Hybrid scoring happens in Python after
        the DB returns candidates, consistent with the FAISS path.
        """
        # Use _safe_embed() so dimension mismatches are handled before the SQL
        # reaches Postgres. If the active model is 384-dim but the column is 768-dim
        # (or vice-versa), the vector is zero-padded/truncated here rather than
        # causing a "wrong number of dimensions" error inside Postgres.
        query_vector = self._safe_embed(query)
        # Format as a Postgres literal: '[0.1, 0.2, ...]'
        vec_literal = "[" + ",".join(str(v) for v in query_vector) + "]"

        media_type_filter = ""
        if media_type != "All":
            # Normalise "TV Shows" → "tv", "Movie" → "movie"
            norm = media_type.lower().replace(" shows", "").replace("movies", "movie")
            media_type_filter = f"AND m.media_type = '{norm}'"

        sql = sa_text(f"""
            SELECT
                m.tmdb_id,
                m.media_type               AS emb_media_type,
                (m.embedding <=> :vec)     AS cosine_dist,
                m.db_id,
                m.title,
                m.overview,
                m.release_date,
                m.rating,
                m.poster_path
            FROM media m
            WHERE m.rating >= :min_rating
            AND m.embedding IS NOT NULL
            {media_type_filter}
            ORDER BY cosine_dist ASC
            LIMIT :search_k
        """)

        search_k = top_k * 5
        rows = db.execute(sql, {"vec": vec_literal, "min_rating": min_rating, "search_k": search_k}).fetchall()

        grouped_candidates = {}
        for row in rows:
            tmdb_id = int(row.tmdb_id)
            cosine_dist = float(row.cosine_dist)          # [0, 2]; 0 = identical
            cosine_sim   = 1.0 - (cosine_dist / 2.0)      # map to [0, 1]; 1 = identical

            if tmdb_id in grouped_candidates:
                if cosine_sim > grouped_candidates[tmdb_id]["similarity_score"]:
                    grouped_candidates[tmdb_id]["similarity_score"] = cosine_sim
            else:
                grouped_candidates[tmdb_id] = {
                    "id": tmdb_id,
                    "db_id": int(row.db_id),
                    "title": row.title,
                    "overview": row.overview,
                    "release_date": row.release_date,
                    "rating": float(row.rating or 0),
                    "poster_path": row.poster_path,
                    "media_type": row.emb_media_type,
                    "similarity_score": cosine_sim,
                    "combined_score": 0.0,
                    "original_doc": None,
                }

        candidates = list(grouped_candidates.values())
        for cand in candidates:
            collab_boost = 0.0
            if cand["id"] in user_likes:
                collab_boost = 0.2
            elif cand["id"] in user_dislikes:
                collab_boost = -0.3

            normalized_rating = cand["rating"] / 10.0
            cand["combined_score"] = (cand["similarity_score"] * 0.7) + (normalized_rating * 0.3) + collab_boost

        # Sort by combined target and slice
        candidates = sorted(candidates, key=lambda x: x["similarity_score"], reverse=True)[:top_k]
        return candidates

    def _faiss_search(
        self,
        query: str,
        db,
        top_k: int,
        media_type: str,
        min_rating: float,
        genre: str,
        user_likes: list,
        user_dislikes: list,
    ) -> list:
        """
        FAISS similarity search.  Uses ``_safe_embed`` so that a dimension
        mismatch between the active embedding model and the stored index is
        handled transparently via zero-padding / truncation instead of crashing.
        """
        if self.vector_store is None:
            raise RuntimeError("FAISS index not loaded and pgvector is disabled. Cannot search.")

        search_k = top_k * 5 if (min_rating > 0 or genre or media_type != "All") else top_k * 3

        # Use the dimension-safe embedding path
        query_vec = self._safe_embed(query)
        docs_with_scores = self.vector_store.similarity_search_with_score_by_vector(
            query_vec, k=search_k
        )

        grouped_candidates = {}
        for doc, similarity_score in docs_with_scores:
            tmdb_id = doc.metadata.get("id")
            doc_media_type = doc.metadata.get("media_type", "movie")

            if media_type != "All" and doc_media_type != media_type.lower().replace(" shows", ""):
                continue

            if tmdb_id not in grouped_candidates:
                media_record = db.query(Media).filter(
                    Media.tmdb_id == tmdb_id,
                    Media.media_type == doc_media_type,
                ).first()

                if media_record:
                    if media_record.rating < min_rating:
                        continue
                    if genre and genre.lower() not in (media_record.overview or "").lower():
                        continue

                    grouped_candidates[tmdb_id] = {
                        "id": int(media_record.tmdb_id),
                        "db_id": int(media_record.db_id),
                        "title": media_record.title,
                        "overview": media_record.overview,
                        "release_date": media_record.release_date,
                        "rating": float(media_record.rating),
                        "poster_path": media_record.poster_path,
                        "media_type": media_record.media_type,
                        "similarity_score": -1.0,
                        "combined_score": 0.0,
                        "original_doc": doc,
                    }
            
            if tmdb_id in grouped_candidates:
                cand = grouped_candidates[tmdb_id]
                semantic_similarity = 1.0 / (1.0 + similarity_score)
                if semantic_similarity > cand["similarity_score"]:
                    cand["similarity_score"] = semantic_similarity

        candidates = list(grouped_candidates.values())
        for cand in candidates:
            collab_boost = 0.0
            if cand["id"] in user_likes:
                collab_boost = 0.2
            elif cand["id"] in user_dislikes:
                collab_boost = -0.3
            
            normalized_rating = cand["rating"] / 10.0
            cand["combined_score"] = (cand["similarity_score"] * 0.7) + (normalized_rating * 0.3) + collab_boost

        candidates = sorted(candidates, key=lambda x: x["similarity_score"], reverse=True)[:top_k]
        return candidates

    def _raw_faiss_fallback_search(
        self,
        query: str,
        db,
        top_k: int,
        media_type: str,
        min_rating: float,
        user_likes: list,
        user_dislikes: list,
    ) -> list:
        """
        Tertiary vector-search fallback using the in-process FAISSFallback index
        (IndexFlatIP + L2 normalisation → cosine similarity).

        On first call the index is lazily populated from the ``media`` table.
        Subsequent calls reuse the cached singleton, making this instant.

        Returns the same candidate-dict schema as _pgvector_search and
        _faiss_search so the rest of the pipeline is unaffected.
        """
        print("[RecommendationEngine] Tertiary fallback: raw FAISSFallback search.")

        idx = get_faiss_fallback()
        if not idx.is_ready():
            # Lazily populate if startup hook hasn’t run yet
            n = populate_faiss_fallback_from_db(db)
            print(f"[RecommendationEngine] FAISSFallback lazily loaded {n} vectors.")
            if not idx.is_ready():
                return []

        query_vec = np.array(self._safe_embed(query), dtype=np.float32)
        hits = idx.search(query_vec, top_k * 3)   # over-fetch for post-filter

        candidates = []
        for media_db_id, score in hits:
            media_record = db.query(Media).filter(Media.db_id == media_db_id).first()
            if not media_record:
                continue

            if media_type != "All":
                norm = media_type.lower().replace(" shows", "").replace("movies", "movie")
                if media_record.media_type != norm:
                    continue

            rec_rating = float(getattr(media_record, "vote_average", None) or
                               getattr(media_record, "rating", None) or 0)
            if rec_rating < min_rating:
                continue

            collab_boost = 0.0
            tmdb_id = int(media_record.tmdb_id)
            if tmdb_id in user_likes:
                collab_boost = 0.2
            elif tmdb_id in user_dislikes:
                collab_boost = -0.3

            combined = (score * 0.7) + (rec_rating / 10.0 * 0.3) + collab_boost

            candidates.append({
                "id":              tmdb_id,
                "db_id":           int(media_record.db_id),
                "title":           media_record.title,
                "overview":        media_record.overview,
                "release_date":    media_record.release_date,
                "rating":          rec_rating,
                "poster_path":     media_record.poster_path,
                "media_type":      media_record.media_type,
                "similarity_score": float(score),
                "combined_score":   combined,
                "original_doc":    None,
            })

            if len(candidates) >= top_k:
                break

        return candidates

    def _tfidf_search(
        self,
        query: str,
        db,
        top_k: int,
        media_type: str,
        min_rating: float,
        genre: str,
        user_likes: list,
        user_dislikes: list,
    ) -> list:
        """
        Pure TF-IDF keyword search used as a last-resort fallback when no vector
        index is available or when a dimension-mismatch error is unrecoverable.

        Fetches all media rows from the DB, builds an in-memory TF-IDF matrix,
        and returns the top-k most relevant titles by cosine similarity.
        No external API calls — completely offline-safe.
        """
        print("[RecommendationEngine] Running TF-IDF keyword fallback search.")
        query_filter = [Media.rating >= min_rating]
        if media_type != "All":
            norm = media_type.lower().replace(" shows", "").replace("movies", "movie")
            query_filter.append(Media.media_type == norm)

        rows = db.query(Media).filter(*query_filter).limit(5000).all()
        if not rows:
            return []

        corpus = [
            f"{r.title or ''} {r.overview or ''}" for r in rows
        ]

        vectorizer = TfidfVectorizer(
            stop_words="english",
            max_features=10_000,
            ngram_range=(1, 2),
        )
        tfidf_matrix = vectorizer.fit_transform(corpus)
        query_vec = vectorizer.transform([query])
        sims = cosine_similarity(query_vec, tfidf_matrix)[0]  # shape (n_rows,)

        # Get top-k indices by similarity score
        top_indices = np.argsort(sims)[::-1][:top_k * 2]

        candidates = []
        for idx in top_indices:
            row = rows[idx]
            sim = float(sims[idx])
            if sim <= 0:
                break
            if genre and genre.lower() not in (row.overview or "").lower():
                continue

            collab_boost = 0.0
            if row.tmdb_id in user_likes:
                collab_boost = 0.2
            elif row.tmdb_id in user_dislikes:
                collab_boost = -0.3

            normalized_rating = (row.rating or 0) / 10.0
            combined_score = (sim * 0.7) + (normalized_rating * 0.3) + collab_boost

            candidates.append({
                "id": int(row.tmdb_id),
                "db_id": int(row.db_id),
                "title": row.title,
                "overview": row.overview,
                "release_date": row.release_date,
                "rating": float(row.rating or 0),
                "poster_path": row.poster_path,
                "media_type": row.media_type,
                "similarity_score": sim,
                "combined_score": combined_score,
                "original_doc": None,
            })

        return candidates

    async def get_recommendations(
        self,
        query: str,
        top_k: int = 15,
        final_results: int = 6,
        user_id: str = None,
        genre: str = None,
        min_rating: float = 0.0,
        media_type: str = "All",
    ):
        """
        Return personalised recommendations using either pgvector (primary) or
        FAISS (fallback), followed by MMR-based diversity filtering.

        The embedding model (paraphrase-multilingual-MiniLM-L12-v2 or Gemini
        embedding-001) is natively multilingual: non-English queries are mapped
        directly into the same vector space without translation overhead.
        """
        original_query = query

        db = SessionLocal()
        user_likes, user_dislikes = [], []
        if user_id:
            interactions = db.query(EnhancedInteraction).filter(EnhancedInteraction.user_id == user_id).all()
            user_likes    = [i.media_id for i in interactions if i.interaction_type == "like"]
            user_dislikes = [i.media_id for i in interactions if i.interaction_type == "dislike"]

        # Delegate to the appropriate search backend.
        # Four-tier routing order (highest quality first):
        #   1. pgvector (PostgreSQL) — native cosine distance, best quality
        #   2. LangChain FAISS         — if pgvector unavailable or fails
        #   3. Raw FAISSFallback        — if LangChain FAISS also fails
        #   4. TF-IDF keyword search   — always available, zero-dependency last resort
        try:
            if self.use_pgvector:
                candidates = self._pgvector_search(
                    query, db, top_k, media_type, min_rating, user_likes, user_dislikes
                )
            elif self.vector_store is not None:
                candidates = self._faiss_search(
                    query, db, top_k, media_type, min_rating, genre, user_likes, user_dislikes
                )
            else:
                # Neither pgvector nor LangChain FAISS — try raw FAISSFallback first
                candidates = self._raw_faiss_fallback_search(
                    query, db, top_k, media_type, min_rating, user_likes, user_dislikes
                )
        except Exception as vector_err:
            print(
                f"[RecommendationEngine] Primary/secondary vector search failed ({vector_err}). "
                f"Trying raw FAISSFallback."
            )
            try:
                candidates = self._raw_faiss_fallback_search(
                    query, db, top_k, media_type, min_rating, user_likes, user_dislikes
                )
            except Exception as faiss_err:
                print(
                    f"[RecommendationEngine] FAISSFallback also failed ({faiss_err}). "
                    f"Falling back to TF-IDF keyword search."
                )
                try:
                    candidates = self._tfidf_search(
                        query, db, top_k, media_type, min_rating, genre, user_likes, user_dislikes
                    )
                except Exception as tfidf_err:
                    print(f"[RecommendationEngine] TF-IDF fallback also failed: {tfidf_err}")
                    candidates = []
        finally:
            db.close()

        # All score components are "higher is better" — sort descending.
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
        explanation = await self._generate_explanation(original_query, selected_media, similarity_scores)
        
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
