"""
Migration script to add video_url and thumbnail_url columns to videos table
"""
import sqlite3
import os

# Database path
db_path = os.path.join(os.path.dirname(__file__), 'data', 'database.db')

def migrate():
    """Add video_url and thumbnail_url columns to videos table"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(videos)")
        columns = [column[1] for column in cursor.fetchall()]

        # Add video_url column if it doesn't exist
        if 'video_url' not in columns:
            print("Adding video_url column...")
            cursor.execute("ALTER TABLE videos ADD COLUMN video_url VARCHAR(500)")
            print("[OK] video_url column added")
        else:
            print("[OK] video_url column already exists")

        # Add thumbnail_url column if it doesn't exist
        if 'thumbnail_url' not in columns:
            print("Adding thumbnail_url column...")
            cursor.execute("ALTER TABLE videos ADD COLUMN thumbnail_url VARCHAR(500)")
            print("[OK] thumbnail_url column added")
        else:
            print("[OK] thumbnail_url column already exists")

        # Update existing videos with video_url based on video_id
        print("Updating existing videos with video URLs...")
        cursor.execute("""
            UPDATE videos
            SET video_url = 'https://www.youtube.com/watch?v=' || video_id
            WHERE video_url IS NULL AND video_id IS NOT NULL
        """)
        updated_count = cursor.rowcount
        print(f"[OK] Updated {updated_count} videos with video URLs")

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
