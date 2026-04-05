from fastapi import APIRouter, UploadFile, File, HTTPException
import google.generativeai as genai
import os
import base64

router = APIRouter()

VISION_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro-vision"]

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
            "Analyze this image and return 5 to 8 comma-separated keywords describing "
            "its cinematic mood, aesthetic, genre, and emotional tone. "
            "Return ONLY a single, comma-separated string of keywords. No explanations."
        )

        # 4. Try each model in order, fall back gracefully
        last_error = None
        for model_name in VISION_MODELS:
            try:
                print(f"Trying model: {model_name}...")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content([
                    prompt,
                    {"mime_type": content_type, "data": contents}
                ])
                keywords = response.text.strip()
                print(f"SUCCESS with {model_name}! Keywords: {keywords}")
                return {"extracted_query": keywords}
            except Exception as e:
                last_error = e
                print(f"Model {model_name} failed: {str(e)}")
                continue

        # 5. All models failed — return a graceful fallback instead of a 500 crash
        print(f"All Vision models failed. Last error: {last_error}")
        return {
            "extracted_query": "dramatic, emotional, cinematic, atmospheric",
            "warning": f"Vision API unavailable ({str(last_error)}). Using generic mood keywords."
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"CRITICAL VISION ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")