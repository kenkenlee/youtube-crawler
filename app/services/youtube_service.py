from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import re

from app.config import settings

logger = logging.getLogger(__name__)


class YouTubeService:
    """YouTube Data API v3 only. No scraping fallbacks."""

    def __init__(self):
        self.api_key = settings.YOUTUBE_API_KEY
        self.youtube = None
        if self.api_key:
            try:
                self.youtube = build('youtube', 'v3', developerKey=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize YouTube API: {e}")
        if not self.youtube:
            raise RuntimeError(
                "YOUTUBE_API_KEY is not configured. Crawling uses the YouTube Data API "
                "exclusively — set YOUTUBE_API_KEY in .env and restart the server."
            )

    def extract_channel_id(self, url: str) -> Optional[str]:
        """Extract channel ID from various YouTube URL formats using the Data API"""
        # Format 1: /channel/UCxxxxxx
        match = re.search(r'youtube\.com/channel/(UC[\w-]+)', url)
        if match:
            return match.group(1)

        # Format 2: Just the channel ID
        match = re.match(r'^(UC[\w-]+)$', url)
        if match:
            return match.group(1)

        # Format 3: @handle  (e.g. https://www.youtube.com/@Fireship)
        match = re.search(r'youtube\.com/@([\w.\-]+)', url)
        if match:
            return self._resolve_handle(match.group(1))

        # Format 4: /user/name  (legacy username)
        match = re.search(r'youtube\.com/user/([\w.\-]+)', url)
        if match:
            return self._resolve_username(match.group(1))

        # Format 5: /c/name  (legacy custom URL — resolve via search)
        match = re.search(r'youtube\.com/c/([\w.\-]+)', url)
        if match:
            return self._search_channel(match.group(1))

        # Last resort: search by whatever query text we have
        return self._search_channel(url)

    def _resolve_handle(self, handle: str) -> Optional[str]:
        """Resolve an @handle to a channel ID via channels.list(forHandle=...)"""
        try:
            response = self.youtube.channels().list(
                part='id',
                forHandle=handle
            ).execute()
            items = response.get('items', [])
            if items:
                return items[0]['id']
        except HttpError as e:
            logger.error(f"YouTube API error resolving handle '{handle}': {e}")
        # Some handles aren't registered — fall back to search
        return self._search_channel(handle)

    def _resolve_username(self, username: str) -> Optional[str]:
        """Resolve a legacy /user/ name to a channel ID via channels.list(forUsername=...)"""
        try:
            response = self.youtube.channels().list(
                part='id',
                forUsername=username
            ).execute()
            items = response.get('items', [])
            if items:
                return items[0]['id']
        except HttpError as e:
            logger.error(f"YouTube API error resolving username '{username}': {e}")
        return self._search_channel(username)

    def _search_channel(self, query: str) -> Optional[str]:
        """Find a channel ID via search (costs 100 quota units — used sparingly)"""
        try:
            response = self.youtube.search().list(
                part='snippet',
                type='channel',
                q=query,
                maxResults=1
            ).execute()
            items = response.get('items', [])
            if items:
                return items[0]['snippet']['channelId'] if 'channelId' in items[0]['snippet'] \
                    else items[0]['id'].get('channelId')
        except HttpError as e:
            logger.error(f"YouTube API error searching for channel '{query}': {e}")
        return None

    def get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Fetch channel metadata using the YouTube Data API"""
        try:
            response = self.youtube.channels().list(
                part='snippet,statistics',
                id=channel_id
            ).execute()

            if response.get('items'):
                item = response['items'][0]
                snippet = item.get('snippet', {})
                statistics = item.get('statistics', {})

                return {
                    'channel_id': channel_id,
                    'channel_name': snippet.get('title', ''),
                    'description': snippet.get('description', ''),
                    'channel_url': f'https://www.youtube.com/channel/{channel_id}',
                    'subscriber_count': int(statistics.get('subscriberCount', 0)),
                    'video_count': int(statistics.get('videoCount', 0)),
                    'thumbnail': snippet.get('thumbnails', {}).get('default', {}).get('url', '')
                }
        except HttpError as e:
            logger.error(f"YouTube API error for channel {channel_id}: {e}")

        return None

    def list_channel_videos(self, channel_id: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Get list of videos from a channel's uploads playlist via the Data API"""
        videos = []

        try:
            response = self.youtube.channels().list(
                part='contentDetails',
                id=channel_id
            ).execute()

            items = response.get('items', [])
            if not items:
                logger.error(f"Channel {channel_id} not found via YouTube API")
                return videos

            uploads_playlist_id = items[0]['contentDetails']['relatedPlaylists'].get('uploads')
            if not uploads_playlist_id:
                logger.warning(f"Channel {channel_id} has no public uploads playlist")
                return videos

            next_page_token = None
            while len(videos) < max_results:
                playlist_request = self.youtube.playlistItems().list(
                    part='snippet,contentDetails',
                    playlistId=uploads_playlist_id,
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=next_page_token
                )
                playlist_response = playlist_request.execute()

                for item in playlist_response.get('items', []):
                    video_id = item['contentDetails']['videoId']
                    snippet = item['snippet']

                    # Skip private/deleted videos that appear as placeholders
                    if snippet.get('title') in ('Private video', 'Deleted video'):
                        continue

                    videos.append({
                        'video_id': video_id,
                        'title': snippet.get('title', ''),
                        'description': snippet.get('description', ''),
                        'published_at': snippet.get('publishedAt', ''),
                        'thumbnail': snippet.get('thumbnails', {}).get('default', {}).get('url', '')
                    })

                next_page_token = playlist_response.get('nextPageToken')
                if not next_page_token:
                    break
        except HttpError as e:
            logger.error(f"YouTube API error listing videos for channel {channel_id}: {e}")

        return videos

    def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific video via the Data API"""
        try:
            response = self.youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=video_id
            ).execute()

            if response.get('items'):
                item = response['items'][0]
                snippet = item.get('snippet', {})
                statistics = item.get('statistics', {})
                content_details = item.get('contentDetails', {})

                # Parse ISO 8601 duration
                duration = self._parse_duration(content_details.get('duration', 'PT0S'))

                # Parse published date
                published_at = snippet.get('publishedAt', '')
                if published_at:
                    published_at = datetime.fromisoformat(published_at.replace('Z', '+00:00'))

                return {
                    'video_id': video_id,
                    'title': snippet.get('title', ''),
                    'description': snippet.get('description', ''),
                    'channel_id': snippet.get('channelId', ''),
                    'channel_title': snippet.get('channelTitle', ''),
                    'duration': duration,
                    'published_at': published_at,
                    'view_count': int(statistics.get('viewCount', 0)),
                    'like_count': int(statistics.get('likeCount', 0)),
                    'comment_count': int(statistics.get('commentCount', 0)),
                    'tags': snippet.get('tags', []),
                    'thumbnail': snippet.get('thumbnails', {}).get('medium', {}).get('url', '')
                }
        except HttpError as e:
            logger.error(f"YouTube API error for video {video_id}: {e}")

        return None

    def _parse_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration to seconds"""
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration_str)
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            return hours * 3600 + minutes * 60 + seconds
        return 0
