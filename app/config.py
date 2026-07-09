"""
Centralized configuration for EduGenie.
Reads all tunables from environment variables (see .env.example).
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    ENABLE_LOCAL_FALLBACK: bool = os.getenv("ENABLE_LOCAL_FALLBACK", "true").lower() == "true"
    LOCAL_MODEL_NAME: str = os.getenv("LOCAL_MODEL_NAME", "MBZUAI/LaMini-Flan-T5-783M")

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Database (for accounts + saved history). Defaults to a local SQLite
    # file so it works with zero setup during development. On Vercel, set
    # DATABASE_URL to a real Postgres connection string (Vercel's built-in
    # Postgres/Neon integration provides this automatically) -- Vercel's
    # filesystem is temporary, so SQLite alone won't keep data on Vercel.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./edugenie.db")

    # Used to sign login session cookies. Set a long random value in
    # production (e.g. `openssl rand -hex 32`) -- the fallback below is
    # fine for local development only.
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production")

    @property
    def has_gemini(self) -> bool:
        return bool(self.GEMINI_API_KEY)


settings = Settings()
