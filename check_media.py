import sqlite3, os, json

DB_PATH = os.path.join(os.path.dirname(__file__), 'mirai.db')
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Check media table PK and structure
info = c.execute("PRAGMA table_info(media)").fetchall()
print("media columns:")
for row in info:
    print(f"  cid={row[0]} name={row[1]} type={row[2]} notnull={row[3]} pk={row[5]}")

# Show a sample row
row = c.execute("SELECT * FROM media LIMIT 1").fetchone()
if row:
    cols = [r[1] for r in info]
    print("\nSample row:")
    for k, v in zip(cols, row):
        val = str(v)[:80] if v else None
        print(f"  {k}: {val}")

conn.close()
