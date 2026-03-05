from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, Table, Index, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Simple database connection for SQLite
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./mirai.db")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Association table for many-to-many relationship between media and streaming platforms
media_platforms = Table(
    'media_platforms',
    Base.metadata,
    Column('media_id', Integer, ForeignKey('media.db_id'), primary_key=True),
    Column('platform_id', Integer, ForeignKey('streaming_platforms.id'), primary_key=True),
    Column('added_at', DateTime, default=datetime.utcnow)
)

# Association table for user watchlists
user_watchlist = Table(
    'user_watchlist',
    Base.metadata,
    Column('user_id', String, ForeignKey('users.user_id'), primary_key=True),
    Column('media_id', Integer, ForeignKey('media.db_id'), primary_key=True),
    Column('added_at', DateTime, default=datetime.utcnow),
    Column('watched', Boolean, default=False),
    Column('watch_date', DateTime, nullable=True)
)

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    preferences = Column(JSON, default=dict)  # Store user preferences as JSON
    language_preference = Column(String, default="en")
    
    # Relationships
    interactions = relationship("EnhancedInteraction", back_populates="user")
    watchlist = relationship("Media", secondary=user_watchlist, back_populates="watchlisted_by")
    reviews = relationship("UserReview", back_populates="user")

class Media(Base):
    __tablename__ = "media"

    db_id = Column(Integer, primary_key=True, index=True)
    tmdb_id = Column(Integer, index=True)
    title = Column(String, index=True)
    overview = Column(Text)
    release_date = Column(String)
    rating = Column(Float)
    poster_path = Column(String)
    media_type = Column(String, default="movie", index=True)
    
    # Enhanced fields
    original_language = Column(String, default="en")
    runtime = Column(Integer, nullable=True)  # minutes
    budget = Column(Integer, nullable=True)
    revenue = Column(Integer, nullable=True)
    status = Column(String, default="released")
    tagline = Column(String, nullable=True)
    genres = Column(JSON, default=list)  # List of genre names
    cast = Column(JSON, default=list)  # List of main cast members
    director = Column(String, nullable=True)
    trailer_url = Column(String, nullable=True)
    imdb_id = Column(String, nullable=True)
    
    # Recommendation features
    popularity_score = Column(Float, default=0.0)
    trending_score = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    platforms = relationship("StreamingPlatform", secondary=media_platforms, back_populates="media")
    interactions = relationship("EnhancedInteraction", back_populates="media")
    watchlisted_by = relationship("User", secondary=user_watchlist, back_populates="watchlist")
    reviews = relationship("UserReview", back_populates="media")

class StreamingPlatform(Base):
    __tablename__ = "streaming_platforms"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True)
    logo_path = Column(String, nullable=True)
    country = Column(String, default="US")
    service_type = Column(String, default="subscription")  # subscription, rental, purchase, free
    price_tier = Column(String, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    media = relationship("Media", secondary=media_platforms, back_populates="platforms")

class EnhancedInteraction(Base):
    __tablename__ = "enhanced_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.user_id"), index=True)
    media_id = Column(Integer, ForeignKey("media.db_id"), index=True)
    interaction_type = Column(String, index=True)  # "like", "dislike", "watch", "rate", "skip"
    rating = Column(Integer, nullable=True)  # 1-10 rating if interaction_type is "rate"
    session_id = Column(String, nullable=True)  # Track user sessions
    timestamp = Column(DateTime, default=datetime.utcnow)
    context = Column(JSON, default=dict)  # Store context like query, filters used, etc.
    
    # Relationships
    user = relationship("User", back_populates="interactions")
    media = relationship("Media", back_populates="interactions")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_interaction', 'user_id', 'interaction_type'),
        Index('idx_media_interaction', 'media_id', 'interaction_type'),
        Index('idx_timestamp', 'timestamp'),
    )

class UserReview(Base):
    __tablename__ = "user_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.user_id"), index=True)
    media_id = Column(Integer, ForeignKey("media.db_id"), index=True)
    review_text = Column(Text, nullable=False)
    rating = Column(Integer, nullable=True)  # 1-10 rating
    sentiment_score = Column(Float, nullable=True)  # -1 to 1, calculated by sentiment analysis
    helpful_votes = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="reviews")
    media = relationship("Media", back_populates="reviews")

class RecommendationCache(Base):
    __tablename__ = "recommendation_cache"
    
    id = Column(Integer, primary_key=True)
    cache_key = Column(String, unique=True, index=True)  # Hash of query + filters + user_id
    user_id = Column(String, nullable=True, index=True)
    query_hash = Column(String, index=True)
    results = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, index=True)
    hit_count = Column(Integer, default=0)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_cache_expiry', 'expires_at'),
    )

class TrendingMedia(Base):
    __tablename__ = "trending_media"
    
    id = Column(Integer, primary_key=True)
    media_id = Column(Integer, ForeignKey("media.db_id"), unique=True, index=True)
    trending_score = Column(Float, default=0.0)
    rank_position = Column(Integer, index=True)
    category = Column(String, default="general")  # general, movies, tv, regional
    region = Column(String, default="global")
    calculated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    media = relationship("Media")

class SearchAnalytics(Base):
    __tablename__ = "search_analytics"
    
    id = Column(Integer, primary_key=True)
    query = Column(String, index=True)
    query_language = Column(String, nullable=True)
    user_id = Column(String, nullable=True, index=True)
    results_count = Column(Integer, default=0)
    clicked_results = Column(JSON, default=list)  # List of media_ids that were clicked/liked
    search_duration_ms = Column(Integer, nullable=True)
    filters_used = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_query_analytics', 'query', 'timestamp'),
        Index('idx_user_analytics', 'user_id', 'timestamp'),
    )

def init_enhanced_db():
    """Initialize all tables with proper indexes"""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session():
    """Get a database session for manual operations"""
    return SessionLocal()