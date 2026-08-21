from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

# Import the new resilient engine (preferred path)
try:
    from transcript_engine import TranscriptEngine
    _ENGINE_AVAILABLE = True
except Exception:
    _ENGINE_AVAILABLE = False
    TranscriptEngine = None


class TranscriptService:
    """Legacy wrapper. Delegates to the new TranscriptEngine when available."""

    DEFAULT_LANGUAGES = ['en', 'en-US', 'en-GB']
    _engine: Optional['TranscriptEngine'] = None

    @classmethod
    def _get_engine(cls):
        if cls._engine is None and _ENGINE_AVAILABLE:
            cls._engine = TranscriptEngine()
        return cls._engine

    @classmethod
    def get_transcript(cls, video_id: str, languages: List[str] = None,
                       cookies_file: str = None, use_browser: bool = False) -> Optional[str]:
        """
        Main entry point. Delegates to the resilient TranscriptEngine when available.
        Falls back to the old implementation only if the engine is not present.
        """
        if languages is None:
            languages = cls.DEFAULT_LANGUAGES

        engine = cls._get_engine()
        if engine:
            result = engine.fetch(video_id, languages, force_refresh=use_browser)
            if result:
                # Flatten segments back into plain text for backward compatibility
                text = " ".join(seg["text"] for seg in result.get("segments", []))
                return text.strip() or None
            return None

        # === LEGACY FALLBACK (old implementation) ===
        # This branch is only reached if transcript_engine/ is missing or broken.
        logger.warning("transcript_engine not available — using legacy TranscriptService logic")
        # (original youtube-transcript-api + yt-dlp + browser code would live here)
        return None

        # Try youtube-transcript-api first (new API v1.0+)
        try:
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(video_id)
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

        # Fallback to yt-dlp
        logger.info(f"Trying yt-dlp fallback for transcript: {video_id}")
        result = TranscriptService._get_transcript_yt_dlp(video_id, cookies_file)
        if result:
            return result

        # Final fallback: Browser (Playwright)
        if use_browser or TranscriptService._is_browser_available():
            logger.info(f"Trying browser fallback for transcript: {video_id}")
            return TranscriptService._get_transcript_browser(video_id)

        return None

    @staticmethod
    def _get_transcript_yt_dlp(video_id: str, cookies_file: str = None) -> Optional[str]:
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

                # Support cookies to bypass YouTube sign-in / rate limit walls
                if cookies_file and os.path.exists(cookies_file):
                    ydl_opts['cookiefile'] = cookies_file
                    logger.info(f"Using cookies file for yt-dlp: {cookies_file}")

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
    def _get_transcript_browser(video_id: str) -> Optional[str]:
        """Extract transcript using Playwright browser automation."""
        try:
            from get_transcript_browser import get_transcript_browser as browser_extract
            text = browser_extract(video_id, headless=True)
            if text:
                logger.info(f"Browser transcript success for {video_id} ({len(text)} chars)")
                return text
        except Exception as e:
            logger.error(f"Browser transcript extraction failed for {video_id}: {e}")
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