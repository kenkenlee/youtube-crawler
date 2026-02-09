#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Import sample data into the database for new deployments.

This script imports channels, videos, and crawl sessions from JSON files
to populate a fresh database with sample data.
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

from app.database import SessionLocal, engine, Base
from app.models import Channel, Video, CrawlSession, SessionVideo


def parse_datetime(date_str):
    """Parse ISO format datetime string."""
    if date_str:
        try:
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None
    return None


def import_channels(db, channels_data):
    """Import channel data."""
    imported = 0
    skipped = 0

    for data in channels_data:
        # Check if channel already exists
        existing = db.query(Channel).filter_by(channel_id=data['channel_id']).first()
        if existing:
            print(f"   Skipping existing channel: {data['channel_name']}")
            skipped += 1
            continue

        channel = Channel(
            channel_id=data['channel_id'],
            channel_name=data['channel_name'],
            channel_url=data['channel_url'],
            description=data.get('description'),
            youtube_channel_id=data.get('youtube_channel_id'),
            thumbnail_url=data.get('thumbnail_url'),
            keywords=data.get('keywords'),
            crawl_enabled=data.get('crawl_enabled', True),
            created_at=parse_datetime(data.get('created_at')),
            last_crawled_at=parse_datetime(data.get('last_crawled_at')),
        )

        db.add(channel)
        imported += 1
        print(f"   Imported channel: {data['channel_name']}")

    db.commit()
    return imported, skipped


def import_videos(db, videos_data):
    """Import video data."""
    imported = 0
    skipped = 0

    for data in videos_data:
        # Check if video already exists
        existing = db.query(Video).filter_by(video_id=data['video_id']).first()
        if existing:
            skipped += 1
            continue

        # Verify channel exists
        channel = db.query(Channel).filter_by(channel_id=data['channel_id']).first()
        if not channel:
            print(f"   Warning: Channel {data['channel_id']} not found for video {data['title']}")
            skipped += 1
            continue

        video = Video(
            video_id=data['video_id'],
            channel_id=channel.id,  # Use internal ID
            title=data['title'],
            description=data.get('description'),
            published_at=parse_datetime(data.get('published_at')),
            duration=data.get('duration'),
            view_count=data.get('view_count'),
            like_count=data.get('like_count'),
            comment_count=data.get('comment_count'),
            tags=data.get('tags'),
            transcript_text=data.get('transcript_text'),
            summary_text=data.get('summary_text'),
            matched_keywords=data.get('matched_keywords'),
            created_at=parse_datetime(data.get('created_at')),
            summary_generated_at=parse_datetime(data.get('summary_generated_at')),
        )

        db.add(video)
        imported += 1

        if imported % 10 == 0:
            print(f"   Imported {imported} videos...")

    db.commit()
    return imported, skipped


def import_sessions(db, sessions_data):
    """Import crawl session data."""
    imported = 0
    skipped = 0

    for data in sessions_data:
        # Check if session already exists
        existing = db.query(CrawlSession).filter_by(session_name=data['session_name']).first()
        if existing:
            skipped += 1
            continue

        session = CrawlSession(
            session_name=data['session_name'],
            status=data.get('status', 'completed'),
            channel_ids=data.get('channel_ids'),
            filter_keywords=data.get('filter_keywords'),
            total_channels=data.get('total_channels', 0),
            processed_channels=data.get('processed_channels', 0),
            total_videos_found=data.get('total_videos_found', 0),
            videos_processed=data.get('videos_processed', 0),
            videos_summarized=data.get('videos_summarized', 0),
            error_count=data.get('error_count', 0),
            error_log=data.get('error_log'),
            created_at=parse_datetime(data.get('created_at')),
            started_at=parse_datetime(data.get('started_at')),
            completed_at=parse_datetime(data.get('completed_at')),
        )

        db.add(session)
        imported += 1
        print(f"   Imported session: {data['session_name']}")

    db.commit()
    return imported, skipped


def main():
    """Import sample data from JSON files."""
    print("Importing sample data into database...")

    # Check if sample_data directory exists
    sample_dir = Path(__file__).parent / 'sample_data'
    if not sample_dir.exists():
        print(f"Error: Sample data directory not found: {sample_dir}")
        print("   Run export_sample_data.py first to create sample data.")
        return

    # Initialize database
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # Load JSON files
        print("\nLoading sample data files...")

        with open(sample_dir / 'channels.json', 'r', encoding='utf-8') as f:
            channels_data = json.load(f)

        with open(sample_dir / 'videos.json', 'r', encoding='utf-8') as f:
            videos_data = json.load(f)

        with open(sample_dir / 'sessions.json', 'r', encoding='utf-8') as f:
            sessions_data = json.load(f)

        # Import data
        print("\nImporting channels...")
        channels_imported, channels_skipped = import_channels(db, channels_data)

        print(f"\nImporting videos...")
        videos_imported, videos_skipped = import_videos(db, videos_data)

        print(f"\nImporting sessions...")
        sessions_imported, sessions_skipped = import_sessions(db, sessions_data)

        # Summary
        print(f"\nImport complete!")
        print(f"\nSummary:")
        print(f"   Channels: {channels_imported} imported, {channels_skipped} skipped")
        print(f"   Videos: {videos_imported} imported, {videos_skipped} skipped")
        print(f"   Sessions: {sessions_imported} imported, {sessions_skipped} skipped")

        if channels_imported > 0 or videos_imported > 0 or sessions_imported > 0:
            print(f"\nSample data successfully imported!")
            print(f"   You can now access the application with sample data.")
        else:
            print(f"\nNo new data was imported (all records already exist).")

    except FileNotFoundError as e:
        print(f"Error: Sample data file not found: {e}")
        print("   Run export_sample_data.py first to create sample data.")
    except Exception as e:
        print(f"Error during import: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
