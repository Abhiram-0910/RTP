"""
MIRAI — SQLAlchemy ORM models.

All models inherit from ``database.Base`` so they are registered with the
shared ``MetaData`` object used by ``init_db()`` to drive ``create_all``.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Media(Base):
    """
    Represents a single movie or TV-show entry ingested from TMDB.

    Columns
    -------
    id              — surrogate primary key (auto-increment)
    tmdb_id         — TMDB's own integer ID (unique, not null)
    title           — localised or original title (up to 500 chars)
    media_type      — ``"movie"`` or ``"tv"``
    overview        — plot summary / synopsis (full text)
    genres          — array of genre label strings, e.g. ``["Action", "Drama"]``
    cast_names      — array of top-billed cast member names
    release_date    — ISO date string ``"YYYY-MM-DD"`` (TV → first air date)
    vote_average    — TMDB weighted average rating (0.0 – 10.0)
    popularity      — TMDB popularity score (unbounded float)
    poster_path     — TMDB poster path fragment, e.g. ``"/abc123.jpg"``
    platforms       — JSONB map of country-code → list of platform names,
                      e.g. ``{"IN": ["Netflix", "Prime Video"]}``
    embedding       — 384-dimension sentence-transformer vector (pgvector)
    created_at      — row creation timestamp (set by the DB server)
    """

    __tablename__ = "media"

    __table_args__ = (
        UniqueConstraint("tmdb_id", name="uq_media_tmdb_id"),
        # B-tree index on tmdb_id for exact-match lookups
        Index("ix_media_tmdb_id", "tmdb_id"),
        # B-tree index on media_type for filtered queries
        Index("ix_media_media_type", "media_type"),
        # B-tree index on media_language for language-preference filters (hi/te/ta/en)
        Index("ix_media_media_language", "media_language"),
        # NOTE: The HNSW index on ``embedding`` is created dynamically by
        # ``init_db()`` after the extension is enabled, because DDL for
        # custom index types (USING hnsw) cannot be expressed via
        # SQLAlchemy's Index() without a registered access method.
    )

    # ------------------------------------------------------------------
    # Primary key
    # ------------------------------------------------------------------
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Surrogate primary key",
    )

    # ------------------------------------------------------------------
    # TMDB identifiers
    # ------------------------------------------------------------------
    tmdb_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="TMDB numeric ID",
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Movie / TV show title",
    )

    media_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment='"movie" or "tv"',
    )

    # ------------------------------------------------------------------
    # Descriptive content
    # ------------------------------------------------------------------
    overview: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Plot summary",
    )

    genres: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        comment="Genre label array",
    )

    cast_names: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        comment="Top-billed cast member names",
    )

    # ------------------------------------------------------------------
    # Release / ratings metadata
    # ------------------------------------------------------------------
    release_date: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="ISO date YYYY-MM-DD; first_air_date for TV",
    )

    vote_average: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="TMDB weighted average rating (0–10)",
    )

    popularity: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="TMDB popularity score",
    )

    # ------------------------------------------------------------------
    # Media assets
    # ------------------------------------------------------------------
    poster_path: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
        comment="TMDB poster path fragment",
    )

    # ------------------------------------------------------------------
    # Streaming platforms
    # ------------------------------------------------------------------
    platforms: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='{"CC": ["Platform", ...]} keyed by ISO country code',
    )

    # ------------------------------------------------------------------
    # Vector embedding
    # ------------------------------------------------------------------
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(384),
        nullable=True,
        comment="384-dim paraphrase-multilingual-MiniLM-L12-v2 embedding",
    )

    embedding_gemini: Mapped[list[float] | None] = mapped_column(
        Vector(768),
        nullable=True,
        comment="768-dim text-embedding-004 fallback embedding",
    )

    # ------------------------------------------------------------------
    # Language metadata
    # ------------------------------------------------------------------
    media_language: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        index=False,   # index is in __table_args__ above
        comment="ISO 639-1 original language from TMDB (e.g. 'hi', 'te', 'ta', 'en')",
    )

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Row insertion timestamp (server-side)",
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"<Media id={self.id} tmdb_id={self.tmdb_id} "
            f'title="{self.title}" type={self.media_type} lang={self.media_language}>'
        )
