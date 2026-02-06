"""
Database migration script to add youtube_channel_id column
"""
import sqlite3
import os

db_path = "data/database.db"

if os.path.exists(db_path):
    print("Migrating database...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(channels)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'youtube_channel_id' not in columns:
            # Add new column
            cursor.execute("ALTER TABLE channels ADD COLUMN youtube_channel_id VARCHAR(255)")

            # Copy existing channel_id to youtube_channel_id for existing records
            cursor.execute("UPDATE channels SET youtube_channel_id = channel_id WHERE youtube_channel_id IS NULL")

            conn.commit()
            print("✓ Added youtube_channel_id column")
            print("✓ Migrated existing data")
        else:
            print("✓ Column already exists, no migration needed")

    except Exception as e:
        print(f"✗ Migration error: {e}")
        conn.rollback()
    finally:
        conn.close()
else:
    print("✓ No existing database, will be created on first run")

print("\nDatabase migration complete!")
