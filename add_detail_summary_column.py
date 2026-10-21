"""Add detail summary columns to the videos table (one-off migration)."""
import sqlite3

DB_PATH = "data/database.db"


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    existing = [r[1] for r in cur.execute("PRAGMA table_info(videos)").fetchall()]
    if "detail_summary" not in existing:
        cur.execute("ALTER TABLE videos ADD COLUMN detail_summary TEXT")
        print("Added column: detail_summary")
    else:
        print("Column detail_summary already exists")
    if "detail_summary_generated_at" not in existing:
        cur.execute("ALTER TABLE videos ADD COLUMN detail_summary_generated_at DATETIME")
        print("Added column: detail_summary_generated_at")
    else:
        print("Column detail_summary_generated_at already exists")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    migrate()
