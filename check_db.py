import sqlite3, os, sys

db_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'mirai.db')
alt_path = os.path.join(os.path.dirname(__file__), 'mirai.db')

path = db_path if os.path.exists(db_path) else (alt_path if os.path.exists(alt_path) else None)

if not path:
    print("No mirai.db found — DB will be created on first backend startup.")
    sys.exit(0)

conn = sqlite3.connect(path)
c = conn.cursor()
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"DB path: {path}")
print(f"Tables: {[t[0] for t in tables]}")
for t in tables:
    count = c.execute(f"SELECT COUNT(*) FROM \"{t[0]}\"").fetchone()[0]
    print(f"  {t[0]}: {count} rows")
conn.close()
