"""
Database Optimization Script
Adds missing indexes to improve query performance
"""
from sqlalchemy import create_engine, text
from app.config import settings

def add_indexes():
    """Add missing indexes to improve query performance"""
    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        print("Adding database indexes for performance optimization...")

        try:
            # Add indexes to videos table
            print("Adding indexes to videos table...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_videos_published_at ON videos(published_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_videos_summary_generated_at ON videos(summary_generated_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_videos_platform ON videos(platform)"))

            # Add indexes to channels table
            print("Adding indexes to channels table...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_channels_last_crawled_at ON channels(last_crawled_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_channels_crawl_enabled ON channels(crawl_enabled)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_channels_platform ON channels(platform)"))

            # Add indexes to crawl_sessions table
            print("Adding indexes to crawl_sessions table...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_crawl_sessions_status ON crawl_sessions(status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_crawl_sessions_created_at ON crawl_sessions(created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_crawl_sessions_completed_at ON crawl_sessions(completed_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_crawl_sessions_started_at ON crawl_sessions(started_at)"))

            # Commit changes
            conn.commit()

            print("[SUCCESS] All indexes added successfully!")
            print("\nIndexes created:")
            print("  - videos: published_at, created_at, summary_generated_at, platform")
            print("  - channels: last_crawled_at, crawl_enabled, platform")
            print("  - crawl_sessions: status, created_at, completed_at, started_at")

        except Exception as e:
            print(f"[ERROR] Error adding indexes: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    add_indexes()
