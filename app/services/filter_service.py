from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class FilterService:
    @staticmethod
    def apply_keyword_filter(video: Dict[str, Any], keywords: List[str]) -> tuple[bool, List[str]]:
        """
        Check if a video matches any of the provided keywords

        Args:
            video: Video dictionary with title, description, tags
            keywords: List of keywords to match against

        Returns:
            Tuple of (matches: bool, matched_keywords: List[str])
        """
        if not keywords:
            return True, []

        matched = []

        # Prepare searchable text
        title = video.get('title', '').lower()
        description = video.get('description', '').lower()
        tags = [tag.lower() for tag in video.get('tags', [])]

        # Check each keyword
        for keyword in keywords:
            keyword_lower = keyword.lower().strip()
            if not keyword_lower:
                continue

            # Check in title
            if keyword_lower in title:
                matched.append(keyword)
                continue

            # Check in description
            if keyword_lower in description:
                matched.append(keyword)
                continue

            # Check in tags
            if any(keyword_lower in tag for tag in tags):
                matched.append(keyword)
                continue

        return len(matched) > 0, matched

    @staticmethod
    def filter_videos_by_keywords(videos: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Filter a list of videos by keywords

        Args:
            videos: List of video dictionaries
            keywords: List of keywords to filter by

        Returns:
            Filtered list of videos with matched_keywords added
        """
        if not keywords:
            return videos

        filtered = []
        for video in videos:
            matches, matched_keywords = FilterService.apply_keyword_filter(video, keywords)
            if matches:
                video['matched_keywords'] = matched_keywords
                filtered.append(video)

        logger.info(f"Filtered {len(videos)} videos to {len(filtered)} matching videos")
        return filtered

    @staticmethod
    def filter_by_duration(videos: List[Dict[str, Any]], min_duration: int = None, max_duration: int = None) -> List[Dict[str, Any]]:
        """
        Filter videos by duration (in seconds)

        Args:
            videos: List of video dictionaries
            min_duration: Minimum duration in seconds
            max_duration: Maximum duration in seconds

        Returns:
            Filtered list of videos
        """
        filtered = []
        for video in videos:
            duration = video.get('duration', 0)

            if min_duration and duration < min_duration:
                continue

            if max_duration and duration > max_duration:
                continue

            filtered.append(video)

        return filtered

    @staticmethod
    def filter_by_views(videos: List[Dict[str, Any]], min_views: int = None, max_views: int = None) -> List[Dict[str, Any]]:
        """
        Filter videos by view count

        Args:
            videos: List of video dictionaries
            min_views: Minimum view count
            max_views: Maximum view count

        Returns:
            Filtered list of videos
        """
        filtered = []
        for video in videos:
            views = video.get('view_count', 0)

            if min_views and views < min_views:
                continue

            if max_views and views > max_views:
                continue

            filtered.append(video)

        return filtered
