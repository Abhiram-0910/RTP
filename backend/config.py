"""
MIRAI — Centralised application settings loaded from environment / .env file.

All modules should import ``settings`` from here rather than reading
``os.environ`` directly, so that defaults, type coercion, and validation
live in one place.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str = Field(
        ...,
        description=(
            "Async PostgreSQL DSN, e.g. "
            "postgresql+asyncpg://user:pass@localhost:5432/mirai"
        ),
    )

    # ------------------------------------------------------------------
    # TMDB
    # ------------------------------------------------------------------
    TMDB_API_KEY: str = Field(..., description="TMDB v3 API read-access key")
    TMDB_BASE_URL: str = "https://api.themoviedb.org/3"
    TMDB_INGEST_TARGET: int = Field(
        10000, description="Target number of titles to ingest"
    )

    # ------------------------------------------------------------------
    # Google Gemini
    # ------------------------------------------------------------------
    GEMINI_API_KEY: str = Field(..., description="Google AI Studio / Gemini API key")
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # ------------------------------------------------------------------
    # App behaviour
    # ------------------------------------------------------------------
    DEBUG: bool = False
    API_VERSION: str = "1.0.0"
    CORS_ORIGINS: list[str] = ["*"]

    # ------------------------------------------------------------------
    # Scoring weights
    # ------------------------------------------------------------------
    WEIGHT_COSINE: float = 0.65
    WEIGHT_POPULARITY: float = 0.25
    WEIGHT_RATING: float = 0.10

    # MMR
    MMR_LAMBDA: float = 0.5
    MMR_CANDIDATE_POOL: int = 20
    MMR_TOP_K: int = 8

    # ------------------------------------------------------------------
    # Cache (TTLCache fallback)
    # ------------------------------------------------------------------
    CACHE_MAX_SIZE: int = 512
    CACHE_TTL_SECONDS: int = 3600  # 1 hour


settings = Settings()  # type: ignore[call-arg]
