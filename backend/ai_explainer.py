import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple

from .config import settings
from .models import Media

logger = logging.getLogger(__name__)

def get_ai_explainer():
    return True

# Language string map to force accurate semantic instruction in the prompt
LANGUAGE_MAPPING = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "ta": "Tamil",
    "default": "English"
}

async def generate_explanations(
    query: str,
    candidates: List[Media],
    detected_language: str,
) -> Tuple[Dict[int, str], str]:
    """
    Generates per-movie explanations via the LLM router (Gemini → Ollama fallback).
    Returns: (explanations_dict, provider_used)
      explanations_dict maps tmdb_id → 2-sentence rationale string.
    """
    from .llm_router import llm_router

    default_explanation = "Recommended based on strong thematic similarity to your query."

    if not candidates:
        return {}, "none"

    candidates_batch = candidates[:5]
    language_name = LANGUAGE_MAPPING.get(detected_language, LANGUAGE_MAPPING["default"])

    # Build prompt lines
    prompt_lines = [
        f'You are Movies and TV shows Recommendation Engine, a cinematic recommendation AI. The user\'s mood query was: "{query}"',
        f'Detected language: {language_name}. Respond entirely in {language_name}.',
        "",
        "For each film below, write exactly 2 sentences:",
        "Sentence 1: How this film's emotional tone or theme matches the user's specific query.",
        "Sentence 2: Mention one specific detail — genre, rating, cast, or director — that reinforces the match.",
        "",
        "Use 'because' or its equivalent. Reference the specific query words. Never write generic praise.",
        "Keep your response concise. Maximum 2 sentences per movie. Do not explain your reasoning process.",
        "",
        "Respond ONLY with valid JSON. No markdown, no preamble, no trailing text.",
        'Format: {"1": "two sentences.", "2": "two sentences."}',
        "",
        "Films:",
    ]

    index_to_tmdb_id: Dict[str, int] = {}

    for idx, media in enumerate(candidates_batch, start=1):
        idx_str = str(idx)
        index_to_tmdb_id[idx_str] = media.tmdb_id

        safe_title = media.title or "Unknown Title"
        safe_overview = (media.overview or "")[:250]
        safe_year = str(media.release_date)[:4] if media.release_date else "N/A"
        safe_rating = round(float(media.rating or 0.0), 1)
        safe_genres = str(media.genres or "Unknown")

        prompt_lines.append(
            f"{idx}. {safe_title} ({safe_year}) — Rating: {safe_rating}/10 — Genres: {safe_genres}\n"
            f"   {safe_overview}"
        )

    prompt_body = "\n".join(prompt_lines)

    # --- Route through LLM router (Gemini → Ollama fallback) ---
    try:
        parsed_json, provider = await llm_router.generate_json(
            prompt=prompt_body,
            max_tokens=800,
            temperature=0.4,
            task_name="per_movie_explanations",
        )

        final_explanations: Dict[int, str] = {}
        for idx_str, explanation in parsed_json.items():
            if idx_str in index_to_tmdb_id:
                final_explanations[index_to_tmdb_id[idx_str]] = str(explanation).strip()

        for tmdb_id in index_to_tmdb_id.values():
            if tmdb_id not in final_explanations:
                final_explanations[tmdb_id] = default_explanation

        return final_explanations, provider

    except Exception as error:
        logger.warning("Explanations failed to generate or parse: %s", error)
        # Rule-based fallback (no LLM needed)
        results: Dict[int, str] = {}
        for m in candidates_batch:
            title = m.title
            if detected_language == "es":
                fallback = f"Esta película ({title}) coincide fuertemente con el estado de ánimo y los temas de su búsqueda. Disfrute de la visualización."
            elif detected_language == "ja":
                fallback = f"この映画（{title}）は、あなたの検索の雰囲気やテーマと強く一致しています。ぜひお楽しみください。"
            else:
                fallback = (
                    f"This title ({title}) strongly matches the mood and narrative themes of your search. "
                    "It offers a compelling cinematic experience tailored to your exact prompt."
                )
            results[m.tmdb_id] = fallback
        return results, "fallback"
