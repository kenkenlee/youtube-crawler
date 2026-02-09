"""
Migration script to add multi-platform support (YouTube, Twitter, Instagram)
"""
import sqlite3
import os

# Database path
db_path = os.path.join(os.path.dirname(__file__), 'data', 'database.db')

def migrate():
    """Add platform columns to channels and videos tables"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check existing columns
        cursor.execute("PRAGMA table_info(channels)")
        channel_columns = [column[1] for column in cursor.fetchall()]

        cursor.execute("PRAGMA table_info(videos)")
        video_columns = [column[1] for column in cursor.fetchall()]

        # Add platform column to channels if it doesn't exist
        if 'platform' not in channel_columns:
            print("Adding platform column to channels table...")
            cursor.execute("ALTER TABLE channels ADD COLUMN platform VARCHAR(50) DEFAULT 'youtube'")
            print("[OK] platform column added to channels")
            
            # Update existing channels to 'youtube'
            cursor.execute("UPDATE channels SET platform = 'youtube' WHERE platform IS NULL")
            print("[OK] Updated existing channels to platform='youtube'")
        else:
            print("[OK] platform column already exists in channels")

        # Add platform column to videos if it doesn't exist
        if 'platform' not in video_columns:
            print("Adding platform column to videos table...")
            cursor.execute("ALTER TABLE videos ADD COLUMN platform VARCHAR(50) DEFAULT 'youtube'")
            print("[OK] platform column added to videos")
            
            # Update existing videos to 'youtube'
            cursor.execute("UPDATE videos SET platform = 'youtube' WHERE platform IS NULL")
            print("[OK] Updated existing videos to platform='youtube'")
        else:
            print("[OK] platform column already exists in videos")

        # Add platform_username column to channels (for Twitter/Instagram handles)
        if 'platform_username' not in channel_columns:
            print("Adding platform_username column to channels table...")
            cursor.execute("ALTER TABLE channels ADD COLUMN platform_username VARCHAR(255)")
            print("[OK] platform_username column added to channels")
        else:
            print("[OK] platform_username column already exists in channels")

        conn.commit()
        print("\n[SUCCESS] Multi-platform migration completed successfully!")
        print("\nSupported platforms:")
        print("  - youtube")
        print("  - twitter")
        print("  - instagram")

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration failed: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("Starting multi-platform migration...\n")
    migrate()
