"""
Centralized configuration for EduGenie.
Reads all tunables from environment variables (see .env.example).
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

    ENABLE_LOCAL_FALLBACK: bool = os.getenv("ENABLE_LOCAL_FALLBACK", "true").lower() == "true"
    LOCAL_MODEL_NAME: str = os.getenv("LOCAL_MODEL_NAME", "MBZUAI/LaMini-Flan-T5-783M")

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    @property
    def has_gemini(self) -> bool:
        return bool(self.GEMINI_API_KEY)


settings = Settings()
