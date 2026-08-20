import yt_dlp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class YouTubeService:
    def __init__(self):
        self.api_key = settings.YOUTUBE_API_KEY
        self.youtube = None
        if self.api_key:
            try:
                self.youtube = build('youtube', 'v3', developerKey=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize YouTube API: {e}")

    def extract_channel_id(self, url: str) -> Optional[str]:
        """Extract channel ID from various YouTube URL formats"""
        import re

        # Try to extract from URL patterns first
        # Format 1: /channel/UCxxxxxx
        match = re.search(r'youtube\.com/channel/(UC[\w-]+)', url)
        if match:
            return match.group(1)

        # Format 2: Just the channel ID
        match = re.match(r'^(UC[\w-]+)$', url)
        if match:
            return match.group(1)

        # For other formats (@username, /c/name, /user/name), use yt-dlp
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info and 'channel_id' in info:
                    return info['channel_id']
                elif info and 'uploader_id' in info:
                    return info['uploader_id']
        except Exception as e:
            logger.error(f"Failed to extract channel ID from {url}: {e}")

        return None

    def get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Fetch channel metadata using YouTube API or yt-dlp fallback"""
        # Try YouTube API first
        if self.youtube:
            try:
                request = self.youtube.channels().list(
                    part='snippet,statistics,contentDetails',
                    id=channel_id
                )
                response = request.execute()

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

        # Fallback to yt-dlp
        try:
            url = f'https://www.youtube.com/channel/{channel_id}'
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    return {
                        'channel_id': channel_id,
                        'channel_name': info.get('uploader', info.get('channel', '')),
                        'description': info.get('description', ''),
                        'channel_url': url,
                        'subscriber_count': info.get('subscriber_count', 0),
                        'video_count': info.get('video_count', 0),
                        'thumbnail': info.get('thumbnail', '')
                    }
        except Exception as e:
            logger.error(f"yt-dlp error for channel {channel_id}: {e}")

        return None

    def list_channel_videos(self, channel_id: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Get list of videos from a channel"""
        videos = []

        # Try YouTube API first
        if self.youtube:
            try:
                # Get uploads playlist ID
                request = self.youtube.channels().list(
                    part='contentDetails',
                    id=channel_id
                )
                response = request.execute()

                if response.get('items'):
                    uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

                    # Get videos from uploads playlist
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

                    return videos
            except HttpError as e:
                logger.error(f"YouTube API error listing videos for channel {channel_id}: {e}")

        # Fallback to yt-dlp
        try:
            url = f'https://www.youtube.com/channel/{channel_id}'
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'playlistend': max_results,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info and 'entries' in info:
                    for entry in info['entries'][:max_results]:
                        if entry:
                            videos.append({
                                'video_id': entry.get('id', ''),
                                'title': entry.get('title', ''),
                                'description': entry.get('description', ''),
                                'published_at': entry.get('upload_date', ''),
                                'thumbnail': entry.get('thumbnail', ''),
                                'duration': entry.get('duration', 0),
                                'view_count': entry.get('view_count', 0)
                            })
        except Exception as e:
            logger.error(f"yt-dlp error listing videos for channel {channel_id}: {e}")

        return videos

    def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific video"""
        # Try YouTube API first
        if self.youtube:
            try:
                request = self.youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=video_id
                )
                response = request.execute()

                if response.get('items'):
                    item = response['items'][0]
                    snippet = item.get('snippet', {})
                    statistics = item.get('statistics', {})
                    content_details = item.get('contentDetails', {})

                    # Parse ISO 8601 duration
                    duration_str = content_details.get('duration', 'PT0S')
                    duration = self._parse_duration(duration_str)

                    # Parse published date
                    published_at = snippet.get('publishedAt', '')
                    if published_at:
                        published_at = datetime.fromisoformat(published_at.replace('Z', '+00:00'))

                    return {
                        'video_id': video_id,
                        'title': snippet.get('title', ''),
                        'description': snippet.get('description', ''),
                        'duration': duration,
                        'published_at': published_at,
                        'view_count': int(statistics.get('viewCount', 0)),
                        'like_count': int(statistics.get('likeCount', 0)),
                        'comment_count': int(statistics.get('commentCount', 0)),
                        'tags': snippet.get('tags', []),
                        'thumbnail': snippet.get('thumbnails', {}).get('default', {}).get('url', '')
                    }
            except HttpError as e:
                logger.error(f"YouTube API error for video {video_id}: {e}")

        # Fallback to yt-dlp
        try:
            url = f'https://www.youtube.com/watch?v={video_id}'
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    published_at = info.get('upload_date', '')
                    if published_at:
                        try:
                            published_at = datetime.strptime(published_at, '%Y%m%d')
                        except:
                            published_at = None

                    return {
                        'video_id': video_id,
                        'title': info.get('title', ''),
                        'description': info.get('description', ''),
                        'duration': info.get('duration', 0),
                        'published_at': published_at,
                        'view_count': info.get('view_count', 0),
                        'like_count': info.get('like_count', 0),
                        'comment_count': info.get('comment_count', 0),
                        'tags': info.get('tags', []),
                        'thumbnail': info.get('thumbnail', '')
                    }
        except Exception as e:
            logger.error(f"yt-dlp error for video {video_id}: {e}")

        return None

    def _parse_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration to seconds"""
        import re
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration_str)
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            return hours * 3600 + minutes * 60 + seconds
        return 0
