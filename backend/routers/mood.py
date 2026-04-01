from fastapi import APIRouter, UploadFile, File, HTTPException
import google.generativeai as genai
import base64
import os

router = APIRouter()

# Ensure Gemini is configured
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@router.post("/api/mood-from-image")
async def mood_from_image(file: UploadFile = File(...)):
    """User uploads an image and gets a localized mood query back."""
    try:
        contents = await file.read()

        # We use Gemini 1.5 Flash as it is extremely fast and natively multimodal
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = (
            "Analyze this image and describe its core mood, genre, themes, and visual style "
            "in 5 to 8 keywords suitable for a movie recommendation search engine. "
            "Return ONLY a single, comma-separated string of keywords. No introductory text."
        )

        # The inline_data part requires base64-encoded bytes
        image_part = {
            "inline_data": {
                "mime_type": file.content_type,
                "data": base64.b64encode(contents).decode("utf-8"),
            }
        }

        response = model.generate_content([image_part, prompt])

        mood_query = response.text.strip()
        return {"extracted_query": mood_query}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")