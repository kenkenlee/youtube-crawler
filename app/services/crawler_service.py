from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import asyncio
import time

from app.models.channel import Channel
from app.models.video import Video
from app.models.crawl_session import CrawlSession, SessionVideo
from app.services.youtube_service import YouTubeService
from app.services.filter_service import FilterService
from app.services.transcript_service import TranscriptService
from app.services.summarizer_service import SummarizerService
from app.config import settings

logger = logging.getLogger(__name__)


class CrawlerService:
    def __init__(self, db: Session):
        self.db = db
        self.youtube_service = YouTubeService()
        self.filter_service = FilterService()
        self.transcript_service = TranscriptService()
        self.summarizer_service = SummarizerService()

    async def start_crawl_session(self, session_id: int) -> bool:
        """
        Start a crawl session

        Args:
            session_id: ID of the crawl session to start

        Returns:
            True if successful, False otherwise
        """
        session = self.db.query(CrawlSession).filter(CrawlSession.id == session_id).first()
        if not session:
            logger.error(f"Session {session_id} not found")
            return False

        # Update session status
        session.status = "running"
        session.started_at = datetime.utcnow()
        self.db.commit()

        try:
            # Get channels to crawl
            channels = self.db.query(Channel).filter(Channel.id.in_(session.channel_ids)).all()
            session.total_channels = len(channels)
            self.db.commit()

            # Crawl each channel
            for channel in channels:
                try:
                    await self.crawl_channel(channel, session)
                    session.processed_channels += 1
                    self.db.commit()

                    # Delay between channels
                    await asyncio.sleep(settings.CRAWL_DELAY_SECONDS)

                except Exception as e:
                    logger.error(f"Error crawling channel {channel.channel_name}: {e}")
                    session.error_count += 1
                    error_msg = f"Channel {channel.channel_name}: {str(e)}\n"
                    session.error_log = (session.error_log or "") + error_msg
                    self.db.commit()

            # Mark session as completed
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Session {session_id} completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error in crawl session {session_id}: {e}")
            session.status = "failed"
            session.completed_at = datetime.utcnow()
            session.error_log = (session.error_log or "") + f"Session error: {str(e)}\n"
            self.db.commit()
            return False

    async def crawl_channel(self, channel: Channel, session: CrawlSession) -> int:
        """
        Crawl a single channel and save videos

        Args:
            channel: Channel object to crawl
            session: Current crawl session

        Returns:
            Number of videos processed
        """
        logger.info(f"Crawling channel: {channel.channel_name}")

        # Use youtube_channel_id if available, otherwise try to extract from URL
        youtube_id = channel.youtube_channel_id
        if not youtube_id:
            youtube_id = self.youtube_service.extract_channel_id(channel.channel_url)
            if youtube_id:
                # Save the extracted ID for future use
                channel.youtube_channel_id = youtube_id
                self.db.commit()

        if not youtube_id:
            logger.error(f"Could not determine YouTube channel ID for {channel.channel_name}")
            return 0

        # Get videos from channel
        videos = self.youtube_service.list_channel_videos(
            youtube_id,
            max_results=settings.MAX_VIDEOS_PER_CHANNEL
        )

        if not videos:
            logger.warning(f"No videos found for channel {channel.channel_name}")
            return 0

        logger.info(f"Found {len(videos)} videos for channel {channel.channel_name}")

        # Apply keyword filter if specified
        if session.filter_keywords:
            videos = self.filter_service.filter_videos_by_keywords(videos, session.filter_keywords)
            logger.info(f"After filtering: {len(videos)} videos")

        session.total_videos_found += len(videos)
        self.db.commit()

        # Process each video
        processed_count = 0
        for video_info in videos:
            try:
                await self.process_video(video_info, channel, session)
                processed_count += 1
                session.videos_processed += 1
                self.db.commit()

            except Exception as e:
                logger.error(f"Error processing video {video_info.get('video_id')}: {e}")
                session.error_count += 1
                self.db.commit()

        # Update channel last crawled time
        channel.last_crawled_at = datetime.utcnow()
        self.db.commit()

        return processed_count

    async def process_video(self, video_info: Dict[str, Any], channel: Channel, session: CrawlSession):
        """
        Process a single video: save to DB, extract transcript, generate summary

        Args:
            video_info: Video information dictionary
            channel: Channel object
            session: Current crawl session
        """
        video_id = video_info.get('video_id')
        if not video_id:
            return

        # Check if video already exists
        existing_video = self.db.query(Video).filter(Video.video_id == video_id).first()

        if existing_video:
            # Update existing video
            video = existing_video
            logger.info(f"Updating existing video: {video.title}")
        else:
            # Use basic info from list_channel_videos (more reliable without API key)
            # Fallback to get_video_details only if needed
            detailed_info = self.youtube_service.get_video_details(video_id)
            
            if detailed_info:
                title = detailed_info.get('title', video_info.get('title', ''))
                description = detailed_info.get('description', video_info.get('description', ''))
                duration = detailed_info.get('duration', video_info.get('duration', 0))
                published_at = detailed_info.get('published_at')
                view_count = detailed_info.get('view_count', video_info.get('view_count', 0))
                like_count = detailed_info.get('like_count', video_info.get('like_count', 0))
                comment_count = detailed_info.get('comment_count', video_info.get('comment_count', 0))
                tags = detailed_info.get('tags', video_info.get('tags', []))
            else:
                # Use whatever info we have from the list
                title = video_info.get('title', '')
                description = video_info.get('description', '')
                duration = video_info.get('duration', 0)
                published_at = None
                view_count = video_info.get('view_count', 0)
                like_count = video_info.get('like_count', 0)
                comment_count = video_info.get('comment_count', 0)
                tags = video_info.get('tags', [])
            
            if not title:
                logger.warning(f"No title for video {video_id}, skipping")
                return

            # FORCE SAVE: Always try to save even with minimal data
            logger.info(f"Force-saving video {video_id}: {title[:50]}...")

            # Create new video
            video = Video(
                channel_id=channel.id,
                video_id=video_id,
                title=title,
                description=description,
                duration=duration,
                published_at=published_at,
                view_count=view_count,
                like_count=like_count,
                comment_count=comment_count,
                tags=tags,
                matched_keywords=video_info.get('matched_keywords', [])
            )
            self.db.add(video)
            self.db.commit()
            self.db.refresh(video)

            logger.info(f"✅ SUCCESSFULLY SAVED video to DB: {video.title[:60]} (id={video.id})")

        # Create session-video relationship
        session_video = SessionVideo(
            session_id=session.id,
            video_id=video.id,
            processing_status="processed"
        )
        self.db.add(session_video)
        self.db.commit()

        # Always extract transcript if not already present
        if not video.transcript_text:
            try:
                transcript = self.transcript_service.get_transcript(video.video_id)
                if transcript:
                    video.transcript_text = transcript
                    self.db.commit()
                    logger.info(f"Extracted transcript for video {video.video_id}")
                else:
                    logger.warning(f"No transcript available for video {video.video_id}")
            except Exception as e:
                logger.error(f"Error extracting transcript for video {video_id}: {e}")

        # Extract transcript and generate summary if auto-summarize is enabled
        if settings.AUTO_SUMMARIZE and not video.summary_text:
            try:
                await self.summarize_video(video, session)
            except Exception as e:
                logger.error(f"Error summarizing video {video_id}: {e}")
                session_video.processing_status = "failed"
                session_video.error_message = str(e)
                self.db.commit()

    async def summarize_video(self, video: Video, session: CrawlSession = None):
        """
        Extract transcript and generate summary for a video

        Args:
            video: Video object to summarize
            session: Optional crawl session for tracking
        """
        logger.info(f"Summarizing video: {video.title}")

        # Extract transcript if not already present
        if not video.transcript_text:
            transcript = self.transcript_service.get_transcript(video.video_id)
            if transcript:
                video.transcript_text = transcript
                self.db.commit()
                logger.info(f"Extracted transcript for video {video.video_id}")
            else:
                logger.warning(f"No transcript available for video {video.video_id}")

        # Generate summary
        if video.transcript_text:
            summary = self.summarizer_service.summarize_transcript(video.transcript_text)
        else:
            # Fallback: generate summary from title and description
            summary = self.summarizer_service.generate_title_summary(video.title, video.description or "")

        if summary:
            video.summary_text = summary
            video.summary_generated_at = datetime.utcnow()
            self.db.commit()

            if session:
                session.videos_summarized += 1
                self.db.commit()

            logger.info(f"Generated summary for video {video.video_id}")
        else:
            logger.warning(f"Failed to generate summary for video {video.video_id}")

    def cancel_session(self, session_id: int) -> bool:
        """
        Cancel a running crawl session

        Args:
            session_id: ID of the session to cancel

        Returns:
            True if successful, False otherwise
        """
        session = self.db.query(CrawlSession).filter(CrawlSession.id == session_id).first()
        if not session:
            return False

        if session.status == "running":
            session.status = "cancelled"
            session.completed_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Session {session_id} cancelled")
            return True

        return False
