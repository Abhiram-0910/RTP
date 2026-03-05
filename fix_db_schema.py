"""
fix_db_schema.py — Add missing columns to existing SQLite DB so it matches enhanced_database.py ORM
"""
import sqlite3
import os

DB_PATH = r'c:\Users\rohan\Downloads\movie-rec-project\mirai.db'

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Get existing columns in media table
existing = [r[1] for r in cur.execute('PRAGMA table_info(media)').fetchall()]
print("Existing media columns:", existing)

# Columns to add if missing
media_cols_to_add = [
    ("original_language", "TEXT DEFAULT 'en'"),
    ("runtime", "INTEGER"),
    ("budget", "INTEGER"),
    ("revenue", "INTEGER"),
    ("status", "TEXT DEFAULT 'released'"),
    ("tagline", "TEXT"),
    ("genres", "TEXT DEFAULT '[]'"),
    ("keywords", "TEXT DEFAULT '[]'"),
    ("cast", "TEXT DEFAULT '[]'"),
    ("director", "TEXT"),
    ("trailer_url", "TEXT"),
    ("imdb_id", "TEXT"),
    ("popularity_score", "REAL DEFAULT 0.0"),
    ("trending_score", "REAL DEFAULT 0.0"),
    ("last_updated", "DATETIME"),
]

for col_name, col_def in media_cols_to_add:
    if col_name not in existing:
        try:
            cur.execute(f"ALTER TABLE media ADD COLUMN {col_name} {col_def}")
            print(f"  Added: {col_name}")
        except Exception as e:
            print(f"  Skip {col_name}: {e}")

# Check/create missing tables
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Existing tables:", tables)

if 'streaming_platforms' not in tables:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS streaming_platforms (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            logo_path TEXT,
            country TEXT DEFAULT 'US',
            service_type TEXT DEFAULT 'subscription',
            price_tier TEXT,
            last_updated DATETIME
        )
    """)
    print("  Created: streaming_platforms")

if 'media_platforms' not in tables:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS media_platforms (
            media_id INTEGER REFERENCES media(db_id),
            platform_id INTEGER REFERENCES streaming_platforms(id),
            added_at DATETIME,
            PRIMARY KEY (media_id, platform_id)
        )
    """)
    print("  Created: media_platforms")

if 'users' not in tables:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            created_at DATETIME,
            preferences TEXT DEFAULT '{}',
            language_preference TEXT DEFAULT 'en'
        )
    """)
    print("  Created: users")

if 'enhanced_interactions' not in tables:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS enhanced_interactions (
            id INTEGER PRIMARY KEY,
            user_id TEXT REFERENCES users(user_id),
            media_id INTEGER REFERENCES media(db_id),
            interaction_type TEXT,
            rating INTEGER,
            session_id TEXT,
            timestamp DATETIME,
            context TEXT DEFAULT '{}'
        )
    """)
    print("  Created: enhanced_interactions")
elif 'interactions' in tables and 'enhanced_interactions' not in tables:
    # copy old interactions
    pass

if 'user_watchlist' not in tables:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_watchlist (
            user_id TEXT REFERENCES users(user_id),
            media_id INTEGER REFERENCES media(db_id),
            added_at DATETIME,
            watched INTEGER DEFAULT 0,
            watch_date DATETIME,
            PRIMARY KEY (user_id, media_id)
        )
    """)
    print("  Created: user_watchlist")

if 'user_reviews' not in tables:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_reviews (
            id INTEGER PRIMARY KEY,
            user_id TEXT REFERENCES users(user_id),
            media_id INTEGER REFERENCES media(db_id),
            review_text TEXT NOT NULL,
            rating INTEGER,
            sentiment_score REAL,
            helpful_votes INTEGER DEFAULT 0,
            created_at DATETIME,
            updated_at DATETIME
        )
    """)
    print("  Created: user_reviews")

if 'recommendation_cache' not in tables:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recommendation_cache (
            id INTEGER PRIMARY KEY,
            cache_key TEXT UNIQUE NOT NULL,
            user_id TEXT,
            query_hash TEXT,
            results TEXT NOT NULL,
            created_at DATETIME,
            expires_at DATETIME,
            hit_count INTEGER DEFAULT 0
        )
    """)
    print("  Created: recommendation_cache")

if 'trending_media' not in tables:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trending_media (
            id INTEGER PRIMARY KEY,
            media_id INTEGER UNIQUE REFERENCES media(db_id),
            trending_score REAL DEFAULT 0.0,
            rank_position INTEGER,
            category TEXT DEFAULT 'general',
            region TEXT DEFAULT 'global',
            calculated_at DATETIME
        )
    """)
    print("  Created: trending_media")

if 'search_analytics' not in tables:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS search_analytics (
            id INTEGER PRIMARY KEY,
            query TEXT,
            query_language TEXT,
            user_id TEXT,
            results_count INTEGER DEFAULT 0,
            clicked_results TEXT DEFAULT '[]',
            search_duration_ms INTEGER,
            filters_used TEXT DEFAULT '{}',
            timestamp DATETIME
        )
    """)
    print("  Created: search_analytics")

# Fix JSON columns - ensure genres/keywords/cast are proper JSON lists not None
print("Fixing NULL JSON columns in media...")
cur.execute("UPDATE media SET genres='[]' WHERE genres IS NULL OR genres=''")
cur.execute("UPDATE media SET keywords='[]' WHERE keywords IS NULL OR keywords=''")
cur.execute("UPDATE media SET cast='[]' WHERE cast IS NULL OR cast=''")
cur.execute("UPDATE media SET popularity_score=0.0 WHERE popularity_score IS NULL")
cur.execute("UPDATE media SET trending_score=0.0 WHERE trending_score IS NULL")

conn.commit()
conn.close()
print("\nDB schema fix complete!")
