"""
Script to add thumbnail_url column to channels table and fetch channel icons
"""
from app.database import SessionLocal, engine
from app.models.channel import Channel
from app.services.youtube_service import YouTubeService
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_thumbnail_column():
    """Add thumbnail_url column to channels table"""
    try:
        with engine.connect() as conn:
            # Check if column exists
            result = conn.execute(text("PRAGMA table_info(channels)"))
            columns = [row[1] for row in result]

            if 'thumbnail_url' not in columns:
                logger.info("Adding thumbnail_url column to channels table...")
                conn.execute(text("ALTER TABLE channels ADD COLUMN thumbnail_url VARCHAR(500)"))
                conn.commit()
                logger.info("✅ Column added successfully")
            else:
                logger.info("✅ Column already exists")
    except Exception as e:
        logger.error(f"Error adding column: {e}")


def fetch_channel_thumbnails():
    """Fetch and update channel thumbnail URLs"""
    db = SessionLocal()
    youtube_service = YouTubeService()

    try:
        channels = db.query(Channel).all()
        logger.info(f"Found {len(channels)} channels to update")

        for channel in channels:
            if channel.youtube_channel_id:
                logger.info(f"Fetching thumbnail for {channel.channel_name}...")

                # Get channel info from YouTube
                channel_info = youtube_service.get_channel_info(channel.youtube_channel_id)

                if channel_info and channel_info.get('thumbnail'):
                    channel.thumbnail_url = channel_info['thumbnail']
                    logger.info(f"✅ Updated thumbnail for {channel.channel_name}: {channel.thumbnail_url}")
                else:
                    logger.warning(f"⚠️ No thumbnail found for {channel.channel_name}")
            else:
                logger.info(f"⏭️ Skipping {channel.channel_name} (no youtube_channel_id)")

        db.commit()
        logger.info("✅ All thumbnails updated")

    except Exception as e:
        logger.error(f"Error fetching thumbnails: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting channel thumbnail update...")
    add_thumbnail_column()
    fetch_channel_thumbnails()
    logger.info("✅ Done!")
