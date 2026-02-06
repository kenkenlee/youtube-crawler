"""
Script to fetch and update channel thumbnail URLs using yt-dlp
"""
from app.database import SessionLocal, engine
from app.models.channel import Channel
from sqlalchemy import text
import yt_dlp
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


def fetch_channel_thumbnail_ytdlp(channel_id):
    """Fetch channel thumbnail using yt-dlp"""
    try:
        url = f'https://www.youtube.com/channel/{channel_id}'
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Try different thumbnail fields
            if info:
                # Try thumbnails array first
                if 'thumbnails' in info and info['thumbnails']:
                    # Get the highest quality thumbnail
                    thumbnails = info['thumbnails']
                    if thumbnails:
                        return thumbnails[-1].get('url', '')

                # Try direct thumbnail field
                if 'thumbnail' in info:
                    return info['thumbnail']

                # Try channel_follower_count as indicator of valid channel
                if 'channel' in info:
                    logger.info(f"Channel found but no thumbnail in standard fields")

    except Exception as e:
        logger.error(f"Error fetching thumbnail with yt-dlp: {e}")

    return None


def update_all_thumbnails():
    """Update thumbnails for all channels"""
    db = SessionLocal()

    try:
        channels = db.query(Channel).all()
        logger.info(f"Found {len(channels)} channels to update")

        for channel in channels:
            if channel.youtube_channel_id:
                logger.info(f"Fetching thumbnail for {channel.channel_name} ({channel.youtube_channel_id})...")

                thumbnail_url = fetch_channel_thumbnail_ytdlp(channel.youtube_channel_id)

                if thumbnail_url:
                    channel.thumbnail_url = thumbnail_url
                    logger.info(f"✅ Updated thumbnail for {channel.channel_name}")
                    logger.info(f"   URL: {thumbnail_url[:80]}...")
                else:
                    # Use a default YouTube icon URL format as fallback
                    # This format works for most channels
                    fallback_url = f"https://yt3.ggpht.com/ytc/{channel.youtube_channel_id}=s88-c-k-c0x00ffffff-no-rj"
                    channel.thumbnail_url = fallback_url
                    logger.warning(f"⚠️ Using fallback URL for {channel.channel_name}")
            else:
                logger.info(f"⏭️ Skipping {channel.channel_name} (no youtube_channel_id)")

        db.commit()
        logger.info("✅ All thumbnails updated")

        # Print results
        logger.info("\n" + "="*60)
        logger.info("RESULTS:")
        logger.info("="*60)
        for channel in channels:
            logger.info(f"{channel.channel_name}: {channel.thumbnail_url}")

    except Exception as e:
        logger.error(f"Error updating thumbnails: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting channel thumbnail update...")
    add_thumbnail_column()
    update_all_thumbnails()
    logger.info("✅ Done!")
