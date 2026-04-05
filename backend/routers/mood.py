from fastapi import APIRouter, UploadFile, File, HTTPException
import google.generativeai as genai
import os
import base64
from backend.rag_engine import RecommendationEngine

router = APIRouter()

VISION_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro-vision"]

def _format_poster_url(path: str) -> str:
    """Formats a TMDB poster path into a full URL."""
    if path:
        return f"https://image.tmdb.org/t/p/w500{path}"
    return ""

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
            raise HTTPException(status_code=400, detail=f"Invalid file type: {content_type}. Please upload an image.")

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

        # 4. Try each model in order, fall back gracefully
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
                keywords = response.text.strip()
                model_used = model_name
                print(f"SUCCESS with {model_name}! Keywords: {keywords}")
                break
            except Exception as e:
                last_error = e
                print(f"Model {model_name} failed: {str(e)}")
                continue

        if not keywords:
            # All models failed — use a graceful fallback keyword set
            keywords = "cinematic, atmospheric, dramatic, emotional"
            model_used = "fallback"
            print(f"All Vision models failed. Last error: {last_error}")

        # 5. Integrate with RecommendationEngine
        engine = RecommendationEngine()
        recommendations = engine.recommend(query=keywords, top_k=24)
        
        # Format the response for the frontend
        formatted_recs = []
        for r in recommendations:
            formatted_recs.append({
                "id": r["id"],
                "title": r["title"],
                "overview": r["overview"],
                "poster_path": _format_poster_url(r["poster_path"]),
                "rating": r["rating"],
                "media_type": r["media_type"],
                "release_date": r["release_date"]
            })

        return {
            "extracted_query": keywords,
            "recommendations": formatted_recs,
            "model_used": model_used
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"CRITICAL VISION ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")