from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# We try to connect to PostgreSQL as requested. 
# If credentials fail, the user can easily switch to SQLite locally by modifying DATABASE_URL.
# Defaulting to an SQLite fallback so the project runs immediately without requiring a running Postgres server.
try:
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./mirai.db")
    
    # SQLite requires check_same_thread=False for FastAPI concurrency
    if DATABASE_URL.startswith("sqlite"):
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(DATABASE_URL)
except Exception as e:
    DATABASE_URL = "sqlite:///./mirai.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
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
    user_id = Column(String, index=True) # Simple string ID for local use
    tmdb_id = Column(Integer, index=True)
    interaction_type = Column(String) # "like", "dislike"
    timestamp = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
