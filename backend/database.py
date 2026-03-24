"""
MIRAI — Database engine, session factory, and startup utilities.
Async SQLAlchemy + asyncpg + pgvector extension bootstrap.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings  # expects DATABASE_URL in .env

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,          # discard stale connections automatically
    pool_recycle=3600,           # recycle connections every hour
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,      # avoid implicit I/O after commit
    autoflush=False,
    autocommit=False,
)

# ---------------------------------------------------------------------------
# Declarative base (shared by all ORM models)
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Common base class for all SQLAlchemy ORM models."""
    pass


# ---------------------------------------------------------------------------
# FastAPI dependency — yields an async session per request
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager / FastAPI dependency that provides a database
    session and ensures it is closed properly after each request.

    Usage in a route::

        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Startup initialisation — called once from the FastAPI lifespan hook
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """
    Run one-time database initialisation steps:

    1. Enable the pgvector extension (idempotent).
    2. Create all ORM-mapped tables that do not yet exist.
    3. Create the HNSW index on the embedding column if absent.

    Call this inside the FastAPI ``lifespan`` startup block.
    """
    # Deferred import to avoid circular dependency at module load time
    from . import models  # noqa: F401 — registers ORM metadata

    async with engine.connect() as ext_conn:
        logger.info("Checking pgvector extension …")
        try:
            # Run without an explicit transaction block to avoid transaction aborted errors
            await ext_conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await ext_conn.commit()
            logger.info("pgvector is enabled.")
        except Exception as e:
            await ext_conn.rollback()
            logger.warning("pgvector extension could not be enabled: %s", e)

    async with engine.begin() as conn:
        # ----------------------------------------------------------------
        # 2. Create tables
        # ----------------------------------------------------------------
        logger.info("Creating missing tables …")
        await conn.run_sync(Base.metadata.create_all)

        # ----------------------------------------------------------------
        # 3. HNSW index
        # ----------------------------------------------------------------
        logger.info("Ensuring HNSW index exists on media.embedding …")
        try:
            await conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1
                            FROM   pg_indexes
                            WHERE  tablename = 'media'
                            AND    indexname = 'ix_media_embedding_hnsw'
                        ) THEN
                            CREATE INDEX ix_media_embedding_hnsw
                            ON media
                            USING hnsw (embedding vector_cosine_ops)
                            WITH  (m = 16, ef_construction = 64);
                        END IF;
                    END
                    $$;
                    """
                )
            )
        except Exception as e:
            logger.warning("HNSW index creation failed (likely because pgvector is missing): %s", e)

    logger.info("Database initialisation complete.")


async def close_db() -> None:
    """Dispose the connection pool on application shutdown."""
    await engine.dispose()
    logger.info("Database connection pool disposed.")
