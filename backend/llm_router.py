"""
llm_router.py — Central LLM router for MIRAI.

Every part of MIRAI that needs LLM generation goes through here.
Primary: Gemini 1.5 Flash (cloud, low-latency)
Fallback: Ollama / deepseek-r1:8b (local, activated on any Gemini failure)

The fallback is completely transparent to the caller:
  text, provider = await llm_router.generate(prompt, task_name="my_task")
  provider is "gemini" or "ollama"
"""

import asyncio
import json
import re
import time
import logging
import google.generativeai as genai
import aiohttp
from typing import Optional
import os
from dotenv import load_dotenv
load_dotenv()

_gemini_key = os.environ.get("GEMINI_API_KEY", "")
if _gemini_key:
    genai.configure(api_key=_gemini_key)

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "deepseek-r1:8b"
GEMINI_MODEL = "gemini-2.0-flash"


class LLMRouter:
    def __init__(self):
        self.gemini_available = True
        self.gemini_cooldown_until: float = 0.0   # epoch seconds
        self.gemini_cooldown_duration: int = 60   # seconds to wait after rate limit hit
        self._ollama_available: Optional[bool] = None  # None = not yet checked

    # ── Ollama availability probe ──────────────────────────────────────────────

    async def _check_ollama(self) -> bool:
        """Check if Ollama is running and deepseek-r1:8b is available."""
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{OLLAMA_BASE_URL}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [m["name"] for m in data.get("models", [])]
                        self._ollama_available = any("deepseek-r1" in m for m in models)
                        if self._ollama_available:
                            logger.info("Ollama fallback: deepseek-r1:8b is available")
                        else:
                            logger.warning(
                                "Ollama running but deepseek-r1:8b not found. "
                                "Available: %s", models
                            )
                        return self._ollama_available
        except Exception as exc:
            logger.warning("Ollama not reachable: %s", exc)
        self._ollama_available = False
        return False

    # ── Gemini cooldown helpers ────────────────────────────────────────────────

    def _gemini_in_cooldown(self) -> bool:
        return time.time() < self.gemini_cooldown_until

    def _trigger_gemini_cooldown(self):
        self.gemini_cooldown_until = time.time() + self.gemini_cooldown_duration
        logger.warning(
            "Gemini rate limit hit. Switching to Ollama for %ds.",
            self.gemini_cooldown_duration,
        )

    # ── Provider call implementations ──────────────────────────────────────────

    async def _call_gemini(
        self,
        prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.4,
    ) -> str:
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        try:
            response = await model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                raise Exception("gemini_rate_limit")
            raise e

    async def _call_ollama(
        self,
        prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.4,
        is_json_task: bool = False,
    ) -> str:
        # Cap temperature — deepseek-r1 gets very verbose above 0.5
        effective_temp = min(temperature, 0.5)

        # Prepend JSON system hint when caller expects JSON output
        if is_json_task:
            prompt = "You are a JSON API. Output only valid JSON with no explanation.\n\n" + prompt

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": effective_temp,
                "num_predict": max_tokens,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),  # local model can be slow
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"Ollama returned HTTP {resp.status}")
                data = await resp.json()
                raw = data.get("response", "")

                # deepseek-r1 wraps reasoning in <think>…</think> — strip ALL occurrences
                raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

                # Edge case: nothing left after stripping → caller should handle gracefully
                return raw

    # ── Public API ─────────────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.4,
        task_name: str = "unknown",
    ) -> tuple[str, str]:
        """
        Generate text using Gemini with automatic Ollama fallback.

        Returns: (response_text, provider_used)
        provider_used is "gemini" or "ollama"
        """
        # Import here to avoid circular imports (metrics_tracker imports nothing from us)
        from backend.metrics_tracker import metrics

        # ── Try Gemini first (unless in cooldown) ────────────────────────────
        if not self._gemini_in_cooldown():
            try:
                start = time.perf_counter()
                text = await self._call_gemini(prompt, max_tokens, temperature)
                elapsed = (time.perf_counter() - start) * 1000
                metrics.record_gemini(success=True, latency_ms=elapsed)
                logger.debug("[%s] Gemini OK (%.0fms)", task_name, elapsed)
                return text, "gemini"
            except Exception as exc:
                error_str = str(exc).lower()
                if any(
                    k in error_str
                    for k in ["429", "quota", "rate", "resource_exhausted", "limit"]
                ):
                    self._trigger_gemini_cooldown()
                else:
                    logger.warning("[%s] Gemini failed (%s), trying Ollama", task_name, exc)
                metrics.record_gemini(success=False, latency_ms=0)

        # ── Fallback to Ollama ────────────────────────────────────────────────
        ollama_ok = await self._check_ollama()
        if not ollama_ok:
            raise Exception(
                "Both Gemini and Ollama are unavailable. "
                "Ensure Ollama is running: 'ollama serve' "
                "and the model is pulled: 'ollama pull deepseek-r1:8b'"
            )

        try:
            start = time.perf_counter()
            text = await self._call_ollama(prompt, max_tokens, temperature)
            elapsed = (time.perf_counter() - start) * 1000
            metrics.record_ollama(success=True, latency_ms=elapsed)
            logger.info("[%s] Ollama fallback used (%.0fms)", task_name, elapsed)
            return text, "ollama"
        except Exception as exc:
            metrics.record_ollama(success=False, latency_ms=0)
            raise Exception(f"Both Gemini and Ollama failed. Last error: {exc}")

    async def generate_json(
        self,
        prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.4,
        task_name: str = "unknown",
    ) -> tuple[dict | list, str]:
        """
        Like generate() but enforces JSON output.
        Strips markdown fences, retries once on parse failure.

        Returns: (parsed_json, provider_used)
        """
        full_prompt = (
            prompt
            + "\n\nCRITICAL: Respond with ONLY valid JSON. "
            "No markdown fences, no explanation, no preamble."
        )

        # Import metrics here too to avoid circular
        from backend.metrics_tracker import metrics

        # Detect if we're going to use Ollama so we can pass is_json_task flag
        _using_ollama = self._gemini_in_cooldown()

        text, provider = await self.generate(full_prompt, max_tokens, temperature, task_name)

        # ── Clean markdown fences ─────────────────────────────────────────────
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned[cleaned.find("\n") + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:cleaned.rfind("```")]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned), provider
        except json.JSONDecodeError:
            # One retry with stricter prompt
            retry_prompt = (
                f"The following is malformed JSON. Fix it and return ONLY the corrected JSON:\n{cleaned}"
            )
            text2, provider2 = await self.generate(retry_prompt, max_tokens, 0.1, task_name + "_retry")
            cleaned2 = text2.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            return json.loads(cleaned2), provider2

    def get_status(self) -> dict:
        """Return LLM status dict for /api/health."""
        in_cd = self._gemini_in_cooldown()
        gemini_status = "cooldown" if in_cd else "active"
        cooldown_remaining = max(0.0, self.gemini_cooldown_until - time.time())
        return {
            "primary": GEMINI_MODEL,
            "fallback": f"ollama/{OLLAMA_MODEL}",
            "gemini_status": gemini_status,
            "ollama_status": "active" if self._ollama_available else "unknown",
            "gemini_cooldown_remaining_seconds": round(cooldown_remaining),
        }


# ── Module-level singleton ─────────────────────────────────────────────────────
llm_router = LLMRouter()
