from fastapi import APIRouter, UploadFile, File, HTTPException
import google.generativeai as genai
import os
from typing import List, Dict, Any

router = APIRouter()

VISION_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro-vision"]


def _format_poster_url(path: str) -> str:
    """Formats a TMDB poster path into a full URL."""
    if path and not str(path).startswith("http"):
        return f"https://image.tmdb.org/t/p/w500{path}"
    return path or ""


def _search_by_keywords(keywords: str, top_k: int = 24) -> List[Dict[str, Any]]:
    """
    Search for movies/shows matching the given keywords.
    Priority: global FAISS vector_store → TF-IDF keyword fallback.
    """
    from backend.enhanced_database import SessionLocal, Media
    from sqlalchemy import func, or_

    results = []

    # ── 1. Try the global FAISS vector_store (already loaded by enhanced_main) ──
    try:
        import backend.enhanced_main as _main
        vs = getattr(_main, "vector_store", None)
        if vs is not None:
            docs_with_scores = vs.similarity_search_with_score(keywords, k=top_k * 3)
            if docs_with_scores:
                tmdb_ids = []
                score_map = {}
                for doc, score in docs_with_scores:
                    tid = doc.metadata.get("tmdb_id") or doc.metadata.get("id")
                    if tid:
                        tid = int(tid)
                        if tid not in score_map:
                            score_map[tid] = float(score)
                            tmdb_ids.append(tid)

                db = SessionLocal()
                try:
                    media_rows = db.query(Media).filter(Media.tmdb_id.in_(tmdb_ids)).all()
                    media_rows.sort(key=lambda m: score_map.get(int(m.tmdb_id), 9999))
                    for m in media_rows[:top_k]:
                        results.append({
                            "id": int(m.tmdb_id),
                            "title": m.title,
                            "overview": m.overview or "",
                            "poster_path": _format_poster_url(m.poster_path),
                            "rating": float(m.rating or 0),
                            "media_type": m.media_type,
                            "release_date": m.release_date or "",
                        })
                finally:
                    db.close()

                if results:
                    return results
    except Exception as e:
        print(f"[MoodSearch] FAISS search failed: {e}")

    # ── 2. TF-IDF keyword fallback (always available) ───────────────────────────
    print("[MoodSearch] Falling back to TF-IDF keyword search.")
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        db = SessionLocal()
        try:
            rows = db.query(Media).filter(
                Media.overview != None,
                Media.overview != "",
            ).order_by(Media.popularity_score.desc()).limit(5000).all()

            if not rows:
                return []

            corpus = [f"{r.title or ''} {r.overview or ''}" for r in rows]
            vectorizer = TfidfVectorizer(stop_words="english", max_features=8000, ngram_range=(1, 2))
            tfidf_matrix = vectorizer.fit_transform(corpus)
            query_vec = vectorizer.transform([keywords])
            sims = cosine_similarity(query_vec, tfidf_matrix)[0]

            top_indices = np.argsort(sims)[::-1][:top_k]
            for idx in top_indices:
                row = rows[idx]
                if float(sims[idx]) <= 0:
                    break
                results.append({
                    "id": int(row.tmdb_id),
                    "title": row.title,
                    "overview": row.overview or "",
                    "poster_path": _format_poster_url(row.poster_path),
                    "rating": float(row.rating or 0),
                    "media_type": row.media_type,
                    "release_date": row.release_date or "",
                })
        finally:
            db.close()
    except Exception as e:
        print(f"[MoodSearch] TF-IDF fallback failed: {e}")

    return results


@router.post("/api/mood-from-image")
async def analyze_mood(file: UploadFile = File(...)):
    print(f"--- INCOMING IMAGE UPLOAD: {file.filename} | type: {file.content_type} ---")
    try:
        # 1. Check API Key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("ERROR: GEMINI_API_KEY is missing from .env file!")
            raise HTTPException(status_code=500, detail="Gemini API Key missing in server config.")

        genai.configure(api_key=api_key)

        # 2. Validate content type
        content_type = file.content_type or "image/jpeg"
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {content_type}. Please upload an image."
            )

        # 3. Read image bytes
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Empty file received.")
        print(f"Successfully read {len(contents)} bytes.")

        prompt = (
            "Analyze this image and return a rich set of keywords describing its cinematic 'mood', 'color palette', "
            "and 'thematic vibe'. Focus on descriptive terms that translate well to finding movies with similar "
            "aesthetics (e.g., 'noir', 'neon-soaked', 'melancholic', 'vibrant', 'high-contrast', 'steampunk', 'gritty'). "
            "Return ONLY a single, comma-separated string of English keywords. No explanations."
        )

        # 4. Try each Gemini vision model in order
        last_error = None
        keywords = ""
        model_used = ""

        for model_name in VISION_MODELS:
            try:
                print(f"Trying model: {model_name}...")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content([
                    prompt,
                    {"mime_type": content_type, "data": contents}
                ])
                # Modern 2.0/2.5 models are chatty. Force cleanup of markdown, list items, and headers.
                raw_text = response.text.replace("\n", ",").replace("*", "").replace("Keywords:", "").replace("Analysis:", "")
                # Clean up double commas and spaces
                keywords = ", ".join(k.strip() for k in raw_text.split(",") if len(k.strip()) > 2)
                
                model_used = model_name
                print(f"SUCCESS with {model_name}! Keywords: {keywords}")
                break
            except Exception as e:
                last_error = e
                print(f"Model {model_name} failed: {str(e)}")
                continue

        if not keywords:
            # All models failed — use a graceful fallback keyword set
            keywords = "cinematic, atmospheric, dramatic, emotional, visually stunning"
            model_used = "fallback"
            print(f"All Vision models failed. Last error: {last_error}")

        # 5. Search for matching movies/shows
        recommendations = _search_by_keywords(keywords, top_k=24)

        print(f"[MoodSearch] Returning {len(recommendations)} recommendations for keywords: {keywords[:80]}")

        return {
            "extracted_query": keywords,
            "recommendations": recommendations,
            "model_used": model_used
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")