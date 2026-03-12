from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Boolean, DateTime, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.sql import text
import os
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional, List

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./mirai.db")

# pgvector integration: install with `pip install pgvector`
try:
    from pgvector.sqlalchemy import Vector
    # Only enable pgvector if we are actually connected to PostgreSQL
    if "postgres" in DATABASE_URL.lower():
        PGVECTOR_AVAILABLE = True
    else:
        PGVECTOR_AVAILABLE = False
        print("[database] Connected to SQLite — pgvector storage disabled, falling back to FAISS.")
except ImportError:
    Vector = None
    PGVECTOR_AVAILABLE = False
    print("[database] pgvector package not installed — vector storage unavailable. Run: pip install pgvector")

# We try to connect to PostgreSQL as requested. 
# If credentials fail, the user can easily switch to SQLite locally by modifying DATABASE_URL.
# Defaulting to an SQLite fallback so the project runs immediately without requiring a running Postgres server.
try:
    # SQLite requires check_same_thread=False for FastAPI concurrency
    if DATABASE_URL.startswith("sqlite"):
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(DATABASE_URL)
except Exception as e:
    DATABASE_URL = "sqlite:///./mirai.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    PGVECTOR_AVAILABLE = False

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Media(Base):
    __tablename__ = "media"

    db_id = Column(Integer, primary_key=True, index=True)
    tmdb_id = Column(Integer, index=True)
    title = Column(String, index=True)
    overview = Column(Text)
    release_date = Column(String)
    rating = Column(Float)
    poster_path = Column(String)
    media_type = Column(String, default="movie", index=True) # "movie" or "tv"

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    tmdb_id = Column(Integer, index=True)
    interaction_type = Column(String)  # "like" | "dislike"
    timestamp = Column(DateTime, default=datetime.utcnow)


class MediaEmbedding(Base):
    """
    Stores the vector embedding for each piece of media.

    Kept in a separate table from `Media` so that the metadata table stays
    lean — embeddings are large (384-768 floats) and are only needed during
    similarity search, not for general metadata queries.

    Dimension notes
    ---------------
    - 384  — paraphrase-multilingual-MiniLM-L12-v2  (HuggingFace, default)
    - 768  — models/embedding-001                   (Gemini, when GEMINI_API_KEY is set)

    Set VECTOR_DIM env var to match whichever model you use.  The default is 384.
    Changing the dimension after the table exists requires a manual column
    migration or a DROP + recreate of media_embeddings.
    """
    __tablename__ = "media_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    tmdb_id = Column(Integer, nullable=False, index=True)
    media_type = Column(String, nullable=False)          # "movie" | "tv"
    chunk_index = Column(Integer, nullable=False, default=0, index=True)
    chunk_text = Column(Text, nullable=True)

    if PGVECTOR_AVAILABLE and Vector is not None:
        _dim = int(os.getenv("VECTOR_DIM", "384"))
        embedding = Column(Vector(_dim), nullable=True)
    else:
        # Graceful fallback: store as opaque text blob (not query-able as vector)
        embedding = Column(Text, nullable=True)

    __table_args__ = (
        # Unique constraint so upsert logic is clean
        __import__('sqlalchemy').UniqueConstraint('tmdb_id', 'media_type', 'chunk_index', name='uq_media_embedding_chunk'),
    )


class User(Base):
    """
    Application user account stored in the database.

    Replaces the previous in-memory USERS_DB dict in auth.py so that users
    persist across restarts and can be managed at runtime (create, disable, etc.).
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)  # "admin" | "user"
    disabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        """Serialize to a plain dict compatible with the auth dependency interface."""
        return {
            "id": self.id,
            "username": self.username,
            "hashed_password": self.hashed_password,
            "role": self.role,
            "disabled": self.disabled,
        }

# ── Query helpers ─────────────────────────────────────────────────────────────

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Return the User ORM object, or None if not found."""
    return db.query(User).filter(User.username == username).first()


def get_embedding_by_tmdb_id(db: Session, tmdb_id: int, media_type: str, chunk_index: int = 0) -> Optional[MediaEmbedding]:
    """Return the MediaEmbedding row, or None."""
    return (
        db.query(MediaEmbedding)
        .filter(
            MediaEmbedding.tmdb_id == tmdb_id, 
            MediaEmbedding.media_type == media_type,
            MediaEmbedding.chunk_index == chunk_index
        )
        .first()
    )


def upsert_embedding(
    db: Session, 
    tmdb_id: int, 
    media_type: str, 
    embedding: List[float], 
    chunk_index: int = 0, 
    chunk_text: Optional[str] = None
) -> None:
    """
    Insert or update the vector embedding for a given (tmdb_id, media_type, chunk_index).
    Used by data_ingestor.py when rebuilding the index.
    """
    existing = get_embedding_by_tmdb_id(db, tmdb_id, media_type, chunk_index)
    if existing:
        existing.embedding = embedding
        existing.chunk_text = chunk_text
    else:
        db.add(MediaEmbedding(
            tmdb_id=tmdb_id, 
            media_type=media_type, 
            embedding=embedding,
            chunk_index=chunk_index,
            chunk_text=chunk_text
        ))
    db.commit()


# ── DB initialisation + admin seeding ─────────────────────────────────────────

def _ensure_pgvector_extension():
    """
    Install the pgvector PostgreSQL extension if it does not already exist.
    This is a no-op on SQLite (which doesn't support extensions).
    """
    url = str(engine.url)
    if url.startswith("sqlite"):
        return
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
        print("[database] pgvector extension ensured.")
    except Exception as e:
        print(f"[database] Could not install pgvector extension: {e}")
        print("[database] Run manually as a superuser: CREATE EXTENSION vector;")


def init_db():
    """
    Create all tables, ensure the pgvector extension is installed, and seed admin.
    Idempotent: safe to call on every startup.
    """
    _ensure_pgvector_extension()
    Base.metadata.create_all(bind=engine)
    _seed_admin()


def _seed_admin():
    """
    Insert the default admin user the first time the DB is initialised.
    Uses passlib to hash the password the same way auth.py does — we import
    lazily to avoid a circular dependency.
    """
    from passlib.context import CryptContext  # local import avoids circular dep

    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "mirai2024")

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == admin_username).first()
        if existing:
            return  # already seeded; nothing to do

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        admin = User(
            username=admin_username,
            hashed_password=pwd_context.hash(admin_password),
            role="admin",
            disabled=False,
        )
        db.add(admin)
        db.commit()
        print(f"[database] Seeded admin user '{admin_username}'.")
    except Exception as e:
        db.rollback()
        print(f"[database] Admin seeding failed: {e}")
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
