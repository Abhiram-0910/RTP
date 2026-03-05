import sqlite3, json

DB_PATH = r'c:\Users\rohan\Downloads\movie-rec-project\mirai.db'
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cols = [r[1] for r in cur.execute('PRAGMA table_info(media)').fetchall()]
tabs = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

with open('schema_out.txt', 'w') as f:
    f.write("MEDIA cols:\n")
    for c in cols:
        f.write(f"  {c}\n")
    f.write("\nTables:\n")
    for t in tabs:
        f.write(f"  {t}\n")
        t_cols = [r[1] for r in cur.execute(f'PRAGMA table_info({t})').fetchall()]
        for tc in t_cols:
            f.write(f"    - {tc}\n")

conn.close()
print("Done, see schema_out.txt")
