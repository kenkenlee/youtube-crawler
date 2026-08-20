from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from typing import Optional, List
import yt_dlp
import tempfile
import os
import re
import logging

logger = logging.getLogger(__name__)


class TranscriptService:
    DEFAULT_LANGUAGES = ['en', 'en-US', 'en-GB']

    @staticmethod
    def get_transcript(video_id: str, languages: List[str] = None) -> Optional[str]:
        """
        Extract transcript - first try youtube-transcript-api, then fall back to yt-dlp
        """
        if languages is None:
            languages = TranscriptService.DEFAULT_LANGUAGES

        # Try youtube-transcript-api first
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = None

            for lang in languages:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    break
                except NoTranscriptFound:
                    continue

            if not transcript:
                for lang in languages:
                    try:
                        transcript = transcript_list.find_generated_transcript([lang])
                        break
                    except NoTranscriptFound:
                        continue

            if not transcript:
                for t in transcript_list:
                    transcript = t
                    break

            if transcript:
                try:
                    transcript_data = transcript.fetch()
                    text = ' '.join([entry.text for entry in transcript_data])
                    if text.strip():
                        logger.info(f"youtube-transcript-api success for {video_id} ({len(text)} chars)")
                        return text.strip()
                except Exception as e:
                    logger.warning(f"youtube-transcript-api fetch failed for {video_id}: {e}")
        except Exception as e:
            logger.warning(f"youtube-transcript-api failed for {video_id}: {e}")

        # Fallback to yt-dlp (more reliable for auto-generated captions)
        logger.info(f"Trying yt-dlp fallback for transcript: {video_id}")
        return TranscriptService._get_transcript_yt_dlp(video_id)

    @staticmethod
    def _get_transcript_yt_dlp(video_id: str) -> Optional[str]:
        """Extract transcript using yt-dlp (downloads subtitle file temporarily)"""
        url = f"https://www.youtube.com/watch?v={video_id}"

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'skip_download': True,
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': ['en', 'en-US', 'en-GB'],
                    'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                # Find subtitle file (.vtt or .srt)
                for filename in os.listdir(tmpdir):
                    if filename.endswith(('.vtt', '.srt')):
                        filepath = os.path.join(tmpdir, filename)
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # Parse VTT/SRT - extract text lines
                        text = TranscriptService._parse_subtitle_file(content)
                        if text:
                            logger.info(f"yt-dlp transcript success for {video_id} ({len(text)} chars)")
                            return text

                logger.warning(f"yt-dlp found no subtitle file for {video_id}")
                return None

        except Exception as e:
            logger.error(f"yt-dlp transcript extraction failed for {video_id}: {e}")
            return None

    @staticmethod
    def _parse_subtitle_file(content: str) -> Optional[str]:
        """Parse VTT or SRT content and return clean text"""
        lines = content.split('\n')
        text_lines = []

        for line in lines:
            line = line.strip()
            # Skip empty lines, timestamps, and headers
            if not line:
                continue
            if '-->' in line:
                continue
            if line.startswith(('WEBVTT', 'Kind:', 'Language:', 'NOTE')):
                continue
            # Remove timestamp tags like <00:00:01.000>
            line = re.sub(r'<\d+:\d+:\d+\.\d+>', '', line)
            # Remove alignment tags
            line = re.sub(r'\{.*?\}', '', line)
            if line:
                text_lines.append(line)

        if text_lines:
            return ' '.join(text_lines)
        return None

    @staticmethod
    def get_available_transcripts(video_id: str) -> list:
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            languages = []
            for transcript in transcript_list:
                languages.append({
                    'language': transcript.language,
                    'language_code': transcript.language_code,
                    'is_generated': transcript.is_generated
                })
            return languages
        except Exception as e:
            logger.error(f"Error getting available transcripts for {video_id}: {e}")
            return []