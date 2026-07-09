"""
AI service layer for EduGenie.

Tries Google Gemini first (cloud, high quality). If no API key is configured,
or the Gemini call fails, and ENABLE_LOCAL_FALLBACK is on, falls back to a
lightweight local model (LaMini-Flan-T5) so the app still works offline /
without a paid key, per the project brief's "lightweight local models and
cloud-based AI services" architecture.
"""
import json
import re
from functools import lru_cache
from typing import Optional

from .config import settings

_gemini_model = None
_local_pipeline = None


class AIServiceError(Exception):
    """Raised when no AI backend could produce a response."""


def _get_gemini_model():
    global _gemini_model
    if _gemini_model is None and settings.has_gemini:
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        _gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL)
    return _gemini_model


def _get_local_pipeline():
    """Lazily load the local fallback model. Heavy — only imported if needed."""
    global _local_pipeline
    if _local_pipeline is None:
        from transformers import pipeline

        _local_pipeline = pipeline(
            "text2text-generation",
            model=settings.LOCAL_MODEL_NAME,
            max_new_tokens=512,
        )
    return _local_pipeline


def generate(prompt: str, *, max_local_tokens: int = 512) -> tuple[str, str]:
    """
    Generate text from a prompt. Returns (text, source) where source is
    "gemini" or "local-lamini" so the UI can show which backend answered.
    """
    if settings.has_gemini:
        try:
            model = _get_gemini_model()
            response = model.generate_content(prompt)
            text = (response.text or "").strip()
            if text:
                return text, "gemini"
        except Exception as exc:  # noqa: BLE001 - we want to fall back on any error
            if not settings.ENABLE_LOCAL_FALLBACK:
                raise AIServiceError(f"Gemini request failed: {exc}") from exc
            # fall through to local model

    if settings.ENABLE_LOCAL_FALLBACK:
        try:
            pipe = _get_local_pipeline()
            result = pipe(prompt, max_new_tokens=max_local_tokens)
            text = result[0]["generated_text"].strip()
            if text:
                return text, "local-lamini"
        except Exception as exc:  # noqa: BLE001
            raise AIServiceError(
                "Both Gemini and the local fallback model failed. "
                f"Local model error: {exc}"
            ) from exc

    raise AIServiceError(
        "No AI backend is available. Set GEMINI_API_KEY in your .env file, "
        "or set ENABLE_LOCAL_FALLBACK=true to use the local model."
    )


def extract_json(text: str) -> dict:
    """
    Model output should be pure JSON, but models (especially the local
    fallback) sometimes wrap it in markdown fences or add stray text.
    This pulls out the first {...} block and parses it defensively.
    """
    cleaned = text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned.strip())
    cleaned = re.sub(r"```$", "", cleaned.strip())
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise
