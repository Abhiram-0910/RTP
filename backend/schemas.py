"""
MIRAI — Pydantic v2 request / response schemas.

All schemas use ``model_config = ConfigDict(from_attributes=True)`` so they
can be constructed directly from SQLAlchemy ORM instances via
``MediaResponse.model_validate(orm_obj)``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Media schemas
# ---------------------------------------------------------------------------


class MediaBase(BaseModel):
    """
    Shared fields used by both create and response schemas.
    All optional here so that partial updates are possible.
    """

    model_config = ConfigDict(from_attributes=True)

    tmdb_id: int = Field(..., description="TMDB numeric identifier", examples=[550])
    title: str = Field(..., max_length=500, description="Movie or TV show title")
    media_type: str = Field(
        ...,
        pattern=r"^(movie|tv)$",
        description='Content type: "movie" or "tv"',
    )
    overview: Optional[str] = Field(None, description="Plot summary / synopsis")
    genres: Optional[List[str]] = Field(None, description="Genre label list")
    cast_names: Optional[List[str]] = Field(None, description="Top-billed cast names")
    release_date: Optional[str] = Field(
        None,
        max_length=20,
        description="ISO date YYYY-MM-DD (first_air_date for TV shows)",
    )
    vote_average: Optional[float] = Field(
        None, ge=0.0, le=10.0, description="TMDB weighted rating"
    )
    popularity: Optional[float] = Field(
        None, ge=0.0, description="TMDB popularity score"
    )
    poster_path: Optional[str] = Field(
        None, max_length=300, description="TMDB poster path fragment"
    )
    platforms: Optional[dict[str, List[str]]] = Field(
        None,
        description='Streaming platforms keyed by ISO country code, e.g. {"IN": ["Netflix"]}',
        examples=[{"IN": ["Netflix", "Prime Video"]}],
    )

    @field_validator("media_type")
    @classmethod
    def validate_media_type(cls, v: str) -> str:
        if v not in {"movie", "tv"}:
            raise ValueError('media_type must be "movie" or "tv"')
        return v


class MediaCreate(MediaBase):
    """
    Schema used when inserting a new Media row (ingest pipeline → DB).
    Embedding is required at creation time.
    """

    embedding: List[float] = Field(
        ...,
        min_length=384,
        max_length=384,
        description="384-dimensional sentence-transformer embedding vector",
    )


class MediaResponse(MediaBase):
    """
    Schema returned to API consumers.
    Embedding is intentionally excluded from API responses (bandwidth).
    """

    id: int = Field(..., description="Surrogate primary key")
    created_at: datetime = Field(..., description="Row insertion timestamp (UTC)")

    # Poster URL helper — construct full CDN URL from the path fragment
    @property
    def poster_url(self) -> Optional[str]:
        if self.poster_path:
            return f"https://image.tmdb.org/t/p/w500{self.poster_path}"
        return None


# ---------------------------------------------------------------------------
# Search / recommendation schemas
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    """
    Payload sent by the frontend to the ``/search`` endpoint.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural-language query describing the desired content",
        examples=["A mind-bending sci-fi movie with an unreliable narrator"],
    )
    platform_filter: Optional[str] = Field(
        None,
        description="Restrict results to titles available on this platform",
        examples=["Netflix"],
    )
    genre_filter: Optional[str] = Field(
        None,
        description="Restrict results to this genre",
        examples=["Action"],
    )
    language: Optional[str] = Field(
        "en",
        min_length=2,
        max_length=10,
        description="BCP-47 language code of the query (auto-detected if omitted)",
        examples=["en", "hi", "fr"],
    )
    country_code: Optional[str] = Field(
        "IN",
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code for Watch Providers lookup",
        examples=["IN", "US", "GB"],
    )
    media_type_filter: Optional[str] = Field(
        None,
        pattern=r"^(movie|tv)$",
        description='Optionally restrict to "movie" or "tv" content',
    )

    @field_validator("country_code", check_fields=False)
    @classmethod
    def uppercase_country(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if v else v

    @field_validator("language")
    @classmethod
    def lowercase_language(cls, v: Optional[str]) -> Optional[str]:
        return v.lower() if v else v


class DeepAnalyzeRequest(BaseModel):
    query: str = Field(..., description="The original user search query")
    candidate_tmdb_ids: List[int] = Field(..., description="Top result TMDB IDs for context")


class RecommendationItem(BaseModel):
    """
    A single ranked recommendation with its blended score and LLM explanation.
    """

    model_config = ConfigDict(from_attributes=True)

    media: MediaResponse = Field(..., description="Full media metadata")
    explanation: str = Field(
        ...,
        description="1-2 sentence LLM-generated rationale of why this title matches the query",
    )
    similarity_factors: Dict[str, float] = Field(
        ...,
        description="Heuristic similarity decomposition: mood, genre, theme, rating",
    )

    # Convenience accessors
    @property
    def title(self) -> str:
        return self.media.title

    @property
    def poster_url(self) -> Optional[str]:
        return self.media.poster_url


class SearchResponse(BaseModel):
    """
    Top-level response envelope returned by the ``/search`` endpoint.
    """

    results: List[RecommendationItem] = Field(
        ...,
        description="Ranked recommendation list (up to 8 items after MMR re-ranking)",
    )
    query_language: str = Field(
        ...,
        description="Detected or provided BCP-47 language code of the user's query",
        examples=["en", "hi"],
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of results returned (len(results))",
    )

    # Ensure ``total`` is always consistent with the actual list length
    @field_validator("total", mode="before")
    @classmethod
    def sync_total(cls, v: Any, info: Any) -> int:  # noqa: ANN401
        results = (info.data or {}).get("results")
        if results is not None:
            return len(results)
        return v


# ---------------------------------------------------------------------------
# Health-check schema (used by GET /health)
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = Field("ok", description='Always "ok" when the service is healthy')
    db: str = Field(..., description='"connected" or error message')
    version: str = Field(..., description="API semantic version string")
