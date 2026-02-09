import yt_dlp
import requests
from bs4 import BeautifulSoup
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import re
import json

logger = logging.getLogger(__name__)


class TwitterService:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }

    def extract_username(self, url: str) -> Optional[str]:
        """Extract username from various Twitter/X.com URL formats"""
        # Format 1: twitter.com/@username or x.com/@username
        match = re.search(r'(?:twitter\.com|x\.com)/@?([a-zA-Z0-9_]+)', url)
        if match:
            return match.group(1)

        # Format 2: Just the username
        match = re.match(r'^@?([a-zA-Z0-9_]+)$', url)
        if match:
            return match.group(1)

        return None

    def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch user profile information using yt-dlp"""
        try:
            url = f'https://x.com/{username}'
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    return {
                        'username': username,
                        'display_name': info.get('uploader', username),
                        'description': info.get('description', ''),
                        'profile_url': url,
                        'thumbnail': info.get('thumbnail', ''),
                        'follower_count': info.get('follower_count', 0),
                    }
        except Exception as e:
            logger.error(f"Error fetching user info for {username}: {e}")

        return None

    def list_user_posts(self, username: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Get list of posts from a user's timeline
        Fetches posts with text, images, and/or videos
        """
        posts = []

        try:
            # Try yt-dlp first for posts with videos
            logger.info(f"Fetching posts from X.com user: {username}")
            url = f'https://x.com/{username}'

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'playlistend': max_results,
                'ignoreerrors': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if info and 'entries' in info:
                    for entry in info['entries'][:max_results]:
                        if entry:
                            post_id = entry.get('id', '')
                            if post_id:
                                # Get detailed info for each post
                                post_url = entry.get('url', f'https://x.com/{username}/status/{post_id}')
                                detailed_post = self.get_post_details(post_url)

                                if detailed_post:
                                    posts.append(detailed_post)
                                else:
                                    # Fallback to basic info
                                    posts.append({
                                        'post_id': post_id,
                                        'title': entry.get('title', ''),
                                        'description': entry.get('description', ''),
                                        'text': entry.get('description', ''),
                                        'published_at': entry.get('upload_date', ''),
                                        'thumbnail': entry.get('thumbnail', ''),
                                        'url': post_url,
                                        'view_count': entry.get('view_count', 0),
                                        'like_count': entry.get('like_count', 0),
                                        'repost_count': entry.get('repost_count', 0),
                                        'reply_count': entry.get('comment_count', 0),
                                        'has_text': bool(entry.get('description')),
                                        'has_images': bool(entry.get('thumbnail')),
                                        'has_video': True,  # yt-dlp only returns video posts
                                        'media_urls': [],
                                    })

            logger.info(f"Found {len(posts)} posts for user {username}")

        except Exception as e:
            logger.error(f"Error listing posts for user {username}: {e}")

        return posts

    def get_post_details(self, post_url: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific post/tweet
        Extracts text, images, and videos
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,  # Get full details
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(post_url, download=False)

                if info:
                    # Extract post ID from URL
                    post_id = info.get('id', '')
                    if not post_id:
                        match = re.search(r'/status/(\d+)', post_url)
                        if match:
                            post_id = match.group(1)

                    # Parse published date
                    published_at = info.get('upload_date', '')
                    if published_at:
                        try:
                            published_at = datetime.strptime(published_at, '%Y%m%d')
                        except:
                            published_at = None

                    # Extract text content
                    text_content = info.get('description', '')
                    title = info.get('title', '')

                    # Extract media information
                    media_urls = []
                    has_video = False
                    has_images = False

                    # Get video formats
                    formats = info.get('formats', [])
                    for fmt in formats:
                        if fmt.get('url') and fmt.get('vcodec') != 'none':
                            media_urls.append({
                                'url': fmt['url'],
                                'type': 'video',
                                'width': fmt.get('width'),
                                'height': fmt.get('height'),
                                'format': fmt.get('format_note', 'video'),
                            })
                            has_video = True

                    # Get thumbnail/image URLs
                    thumbnails = info.get('thumbnails', [])
                    for thumb in thumbnails:
                        if thumb.get('url'):
                            media_urls.append({
                                'url': thumb['url'],
                                'type': 'image',
                                'width': thumb.get('width'),
                                'height': thumb.get('height'),
                            })
                            has_images = True

                    # Remove duplicate media URLs
                    seen_urls = set()
                    unique_media = []
                    for media in media_urls:
                        if media['url'] not in seen_urls:
                            seen_urls.add(media['url'])
                            unique_media.append(media)

                    return {
                        'post_id': post_id,
                        'title': title,
                        'description': text_content,
                        'text': text_content,
                        'published_at': published_at,
                        'view_count': info.get('view_count', 0),
                        'like_count': info.get('like_count', 0),
                        'repost_count': info.get('repost_count', 0),
                        'reply_count': info.get('comment_count', 0),
                        'thumbnail': info.get('thumbnail', ''),
                        'url': post_url,
                        'media_urls': unique_media,
                        'uploader': info.get('uploader', ''),
                        'uploader_id': info.get('uploader_id', ''),
                        'has_text': bool(text_content),
                        'has_images': has_images,
                        'has_video': has_video,
                    }
        except Exception as e:
            logger.error(f"Error fetching post details for {post_url}: {e}")

        return None

    def extract_post_id(self, url: str) -> Optional[str]:
        """Extract post ID from Twitter/X.com URL"""
        match = re.search(r'/status/(\d+)', url)
        if match:
            return match.group(1)
        return None

    def format_post_content(self, post_data: Dict[str, Any]) -> str:
        """
        Format post content with text, images, and videos
        Returns a formatted string with all content
        """
        content_parts = []

        # Add text content
        if post_data.get('text'):
            content_parts.append(f"[Tweet Text]\n{post_data['text']}")

        # Add media information
        media_urls = post_data.get('media_urls', [])
        if media_urls:
            content_parts.append("\n[Media Content]")

            # Group by type
            images = [m for m in media_urls if m['type'] == 'image']
            videos = [m for m in media_urls if m['type'] == 'video']

            if images:
                content_parts.append(f"\nImages ({len(images)}):")
                for i, img in enumerate(images, 1):
                    content_parts.append(f"  {i}. {img['url']}")

            if videos:
                content_parts.append(f"\nVideos ({len(videos)}):")
                for i, vid in enumerate(videos, 1):
                    content_parts.append(f"  {i}. {vid['url']} ({vid.get('format', 'video')})")

        # Add engagement stats
        stats = []
        if post_data.get('view_count'):
            stats.append(f"Views: {post_data['view_count']:,}")
        if post_data.get('like_count'):
            stats.append(f"Likes: {post_data['like_count']:,}")
        if post_data.get('repost_count'):
            stats.append(f"Retweets: {post_data['repost_count']:,}")
        if post_data.get('reply_count'):
            stats.append(f"Replies: {post_data['reply_count']:,}")

        if stats:
            content_parts.append(f"\n[Engagement]\n{' | '.join(stats)}")

        return "\n".join(content_parts)

