#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export sample data from the database for deployment.

This script exports channels, videos, and crawl sessions to JSON files
that can be used as sample data for new deployments.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from app.database import SessionLocal
from app.models import Channel, Video, CrawlSession, SessionVideo


def serialize_datetime(obj):
    """Convert datetime objects to ISO format strings."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def export_channels(db, limit=None):
    """Export channel data."""
    query = db.query(Channel).order_by(Channel.id)
    if limit:
        query = query.limit(limit)

    channels = []
    for channel in query.all():
        channels.append({
            'channel_id': channel.channel_id,
            'channel_name': channel.channel_name,
            'channel_url': channel.channel_url,
            'description': channel.description,
            'youtube_channel_id': channel.youtube_channel_id,
            'thumbnail_url': channel.thumbnail_url,
            'keywords': channel.keywords,
            'crawl_enabled': channel.crawl_enabled,
            'created_at': channel.created_at,
            'last_crawled_at': channel.last_crawled_at,
        })

    return channels


def export_videos(db, limit=None):
    """Export video data."""
    query = db.query(Video).order_by(Video.id)
    if limit:
        query = query.limit(limit)

    videos = []
    for video in query.all():
        videos.append({
            'video_id': video.video_id,
            'channel_id': video.channel_id,
            'title': video.title,
            'description': video.description,
            'published_at': video.published_at,
            'duration': video.duration,
            'view_count': video.view_count,
            'like_count': video.like_count,
            'comment_count': video.comment_count,
            'tags': video.tags,
            'transcript_text': video.transcript_text[:500] if video.transcript_text else None,  # Truncate for sample
            'summary_text': video.summary_text,
            'matched_keywords': video.matched_keywords,
            'created_at': video.created_at,
            'summary_generated_at': video.summary_generated_at,
        })

    return videos


def export_sessions(db, limit=None):
    """Export crawl session data."""
    query = db.query(CrawlSession).order_by(CrawlSession.id)
    if limit:
        query = query.limit(limit)

    sessions = []
    for session in query.all():
        sessions.append({
            'session_name': session.session_name,
            'status': session.status,
            'channel_ids': session.channel_ids,
            'filter_keywords': session.filter_keywords,
            'total_channels': session.total_channels,
            'processed_channels': session.processed_channels,
            'total_videos_found': session.total_videos_found,
            'videos_processed': session.videos_processed,
            'videos_summarized': session.videos_summarized,
            'error_count': session.error_count,
            'error_log': session.error_log,
            'created_at': session.created_at,
            'started_at': session.started_at,
            'completed_at': session.completed_at,
        })

    return sessions


def main():
    """Export sample data to JSON files."""
    print("Exporting sample data from database...")

    # Create sample_data directory
    sample_dir = Path(__file__).parent / 'sample_data'
    sample_dir.mkdir(exist_ok=True)

    db = SessionLocal()

    try:
        # Export data with limits for sample purposes
        print("Exporting channels...")
        channels = export_channels(db, limit=10)

        print("Exporting videos...")
        videos = export_videos(db, limit=50)

        print("Exporting sessions...")
        sessions = export_sessions(db, limit=10)

        # Save to JSON files
        with open(sample_dir / 'channels.json', 'w', encoding='utf-8') as f:
            json.dump(channels, f, indent=2, default=serialize_datetime, ensure_ascii=False)

        with open(sample_dir / 'videos.json', 'w', encoding='utf-8') as f:
            json.dump(videos, f, indent=2, default=serialize_datetime, ensure_ascii=False)

        with open(sample_dir / 'sessions.json', 'w', encoding='utf-8') as f:
            json.dump(sessions, f, indent=2, default=serialize_datetime, ensure_ascii=False)

        # Create metadata file
        metadata = {
            'exported_at': datetime.now(),
            'counts': {
                'channels': len(channels),
                'videos': len(videos),
                'sessions': len(sessions),
            },
            'note': 'This is sample data for demonstration purposes. Transcripts are truncated to 500 characters.',
        }

        with open(sample_dir / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, default=serialize_datetime)

        print(f"\nExport complete!")
        print(f"Sample data saved to: {sample_dir}")
        print(f"   - Channels: {len(channels)}")
        print(f"   - Videos: {len(videos)}")
        print(f"   - Sessions: {len(sessions)}")

    except Exception as e:
        print(f"Error during export: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
