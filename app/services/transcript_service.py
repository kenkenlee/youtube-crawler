from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TranscriptService:
    @staticmethod
    def get_transcript(video_id: str, languages: list = None) -> Optional[str]:
        """
        Extract transcript from a YouTube video

        Args:
            video_id: YouTube video ID
            languages: List of preferred languages (default: ['en'])

        Returns:
            Transcript text as a single string, or None if not available
        """
        if languages is None:
            languages = ['en']

        try:
            # Get transcript list
            transcript_list = YouTubeTranscriptApi().list(video_id)

            # Try to get transcript in preferred languages
            transcript = None
            for lang in languages:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    break
                except NoTranscriptFound:
                    continue

            # If no transcript in preferred languages, try auto-generated English
            if not transcript:
                try:
                    transcript = transcript_list.find_generated_transcript(['en'])
                except NoTranscriptFound:
                    pass

            # If still no transcript, get any available transcript
            if not transcript:
                try:
                    transcript = transcript_list.find_transcript(transcript_list._manually_created_transcripts.keys())
                except:
                    try:
                        transcript = transcript_list.find_generated_transcript(transcript_list._generated_transcripts.keys())
                    except:
                        pass

            if transcript:
                # Fetch and format transcript
                transcript_data = transcript.fetch()
                text = ' '.join([entry.text for entry in transcript_data])
                return text.strip()

            logger.warning(f"No transcript found for video {video_id}")
            return None

        except TranscriptsDisabled:
            logger.warning(f"Transcripts are disabled for video {video_id}")
            return None
        except Exception as e:
            logger.error(f"Error extracting transcript for video {video_id}: {e}")
            return None

    @staticmethod
    def get_available_transcripts(video_id: str) -> list:
        """
        Get list of available transcript languages for a video

        Args:
            video_id: YouTube video ID

        Returns:
            List of available language codes
        """
        try:
            transcript_list = YouTubeTranscriptApi().list(video_id)
            languages = []

            # Get manually created transcripts
            for transcript in transcript_list._manually_created_transcripts.values():
                languages.append({
                    'language': transcript.language,
                    'language_code': transcript.language_code,
                    'is_generated': False
                })

            # Get auto-generated transcripts
            for transcript in transcript_list._generated_transcripts.values():
                languages.append({
                    'language': transcript.language,
                    'language_code': transcript.language_code,
                    'is_generated': True
                })

            return languages
        except Exception as e:
            logger.error(f"Error getting available transcripts for video {video_id}: {e}")
            return []
