"""
Migration script to add max_videos_per_crawl column to crawl_sessions table
"""
import sqlite3
import os

# Database path
db_path = os.path.join(os.path.dirname(__file__), 'data', 'database.db')

def migrate():
    """Add max_videos_per_crawl column to crawl_sessions table"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(crawl_sessions)")
        columns = [column[1] for column in cursor.fetchall()]

        # Add max_videos_per_crawl column if it doesn't exist
        if 'max_videos_per_crawl' not in columns:
            print("Adding max_videos_per_crawl column...")
            cursor.execute("ALTER TABLE crawl_sessions ADD COLUMN max_videos_per_crawl INTEGER DEFAULT 5")
            print("[OK] max_videos_per_crawl column added")
        else:
            print("[OK] max_videos_per_crawl column already exists")

        conn.commit()
        print("\n[SUCCESS] Migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration failed: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("Starting database migration...\n")
    migrate()
