"""
migrate_schema.py — Safe schema migration for MIRAI.
Adds any missing columns to the existing media table without dropping data.
Run once: python migrate_schema.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'mirai.db')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'mirai.db')

print(f"Migrating: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Get existing columns
c.execute("PRAGMA table_info(media)")
existing_cols = {row[1] for row in c.fetchall()}
print(f"Existing columns: {sorted(existing_cols)}")

# Columns to add if missing (name, type, default)
new_columns = [
    ("keywords",        "TEXT",    "NULL"),
    ("cast",            "TEXT",    "NULL"),
    ("director",        "TEXT",    "NULL"),
    ("tagline",         "TEXT",    "NULL"),
    ("imdb_id",         "TEXT",    "NULL"),
    ("runtime",         "INTEGER", "NULL"),
    ("budget",          "INTEGER", "NULL"),
    ("revenue",         "INTEGER", "NULL"),
    ("status",          "TEXT",    "'Released'"),
    ("last_updated",    "TEXT",    "NULL"),
    ("db_id",           "INTEGER", "NULL"),   # may already exist as rowid alias
]

added = []
for col_name, col_type, default in new_columns:
    if col_name not in existing_cols and col_name != "db_id":
        try:
            c.execute(f"ALTER TABLE media ADD COLUMN {col_name} {col_type} DEFAULT {default}")
            added.append(col_name)
            print(f"  + Added column: {col_name}")
        except Exception as e:
            print(f"  ! Could not add {col_name}: {e}")

# Also check for genres column — may store as JSON or comma-separated
if "genres" not in existing_cols:
    c.execute("ALTER TABLE media ADD COLUMN genres TEXT DEFAULT NULL")
    added.append("genres")
    print("  + Added column: genres")

# Check other tables exist; create if not
tables = {row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

if "users" not in tables:
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        created_at TEXT,
        preferences TEXT DEFAULT '{}',
        language_preference TEXT DEFAULT 'en'
    )""")
    print("  + Created table: users")

if "streaming_platforms" not in tables:
    c.execute("""CREATE TABLE IF NOT EXISTS streaming_platforms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        logo_path TEXT,
        country TEXT DEFAULT 'US',
        service_type TEXT DEFAULT 'subscription',
        price_tier TEXT,
        last_updated TEXT
    )""")
    print("  + Created table: streaming_platforms")

if "media_platforms" not in tables:
    c.execute("""CREATE TABLE IF NOT EXISTS media_platforms (
        media_id INTEGER,
        platform_id INTEGER,
        added_at TEXT,
        PRIMARY KEY (media_id, platform_id)
    )""")
    print("  + Created table: media_platforms")

if "enhanced_interactions" not in tables:
    c.execute("""CREATE TABLE IF NOT EXISTS enhanced_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        media_id INTEGER,
        interaction_type TEXT,
        rating INTEGER,
        session_id TEXT,
        timestamp TEXT,
        context TEXT DEFAULT '{}'
    )""")
    print("  + Created table: enhanced_interactions")

if "user_reviews" not in tables:
    c.execute("""CREATE TABLE IF NOT EXISTS user_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        media_id INTEGER,
        review_text TEXT,
        rating INTEGER,
        sentiment_score REAL,
        helpful_votes INTEGER DEFAULT 0,
        created_at TEXT,
        updated_at TEXT
    )""")
    print("  + Created table: user_reviews")

if "recommendation_cache" not in tables:
    c.execute("""CREATE TABLE IF NOT EXISTS recommendation_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cache_key TEXT UNIQUE,
        user_id TEXT,
        query_hash TEXT,
        results TEXT,
        created_at TEXT,
        expires_at TEXT,
        hit_count INTEGER DEFAULT 0
    )""")
    print("  + Created table: recommendation_cache")

if "trending_media" not in tables:
    c.execute("""CREATE TABLE IF NOT EXISTS trending_media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_id INTEGER UNIQUE,
        trending_score REAL DEFAULT 0,
        rank_position INTEGER,
        category TEXT DEFAULT 'general',
        region TEXT DEFAULT 'global',
        calculated_at TEXT
    )""")
    print("  + Created table: trending_media")

if "search_analytics" not in tables:
    c.execute("""CREATE TABLE IF NOT EXISTS search_analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT,
        query_language TEXT,
        user_id TEXT,
        results_count INTEGER DEFAULT 0,
        clicked_results TEXT DEFAULT '[]',
        search_duration_ms INTEGER,
        filters_used TEXT DEFAULT '{}',
        timestamp TEXT
    )""")
    print("  + Created table: search_analytics")

if "user_watchlist" not in tables:
    c.execute("""CREATE TABLE IF NOT EXISTS user_watchlist (
        user_id TEXT,
        media_id INTEGER,
        added_at TEXT,
        watched INTEGER DEFAULT 0,
        watch_date TEXT,
        PRIMARY KEY (user_id, media_id)
    )""")
    print("  + Created table: user_watchlist")

conn.commit()
conn.close()

if added:
    print(f"\nMigration complete. Added {len(added)} columns: {added}")
else:
    print("\nNo new columns needed — schema already up to date.")
