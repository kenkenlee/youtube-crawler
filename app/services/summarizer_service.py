from openai import OpenAI
from typing import Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class SummarizerService:
    def __init__(self):
        self.client = None
        self.model = settings.OPENAI_MODEL

        # Use DeepSeek if enabled, otherwise use OpenAI
        if settings.USE_DEEPSEEK and settings.DEEPSEEK_API_KEY:
            try:
                self.client = OpenAI(
                    api_key=settings.DEEPSEEK_API_KEY,
                    base_url=settings.DEEPSEEK_BASE_URL
                )
                self.model = settings.DEEPSEEK_MODEL
                logger.info("Initialized DeepSeek API client")
            except Exception as e:
                logger.error(f"Failed to initialize DeepSeek client: {e}")
        elif settings.OPENAI_API_KEY:
            try:
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
                self.model = settings.OPENAI_MODEL
                logger.info("Initialized OpenAI API client")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")

    def summarize_transcript(self, transcript: str, style: str = None) -> Optional[str]:
        """
        Generate a summary of a video transcript using OpenAI

        Args:
            transcript: The video transcript text
            style: Summary style (concise/detailed/bullet_points)

        Returns:
            Summary text or None if failed
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return None

        if not transcript or len(transcript.strip()) == 0:
            logger.warning("Empty transcript provided")
            return None

        style = style or settings.SUMMARY_STYLE

        # Prepare prompt based on style
        prompts = {
            'concise': "Provide a concise 2-3 sentence summary of the following video transcript:",
            'detailed': "Provide a detailed summary of the following video transcript, including main points and key takeaways:",
            'bullet_points': "Summarize the following video transcript as a list of bullet points covering the main topics:"
        }

        prompt = prompts.get(style, prompts['concise'])

        # Handle long transcripts by chunking
        max_chars = 12000  # Leave room for prompt and response
        if len(transcript) > max_chars:
            return self.summarize_long_transcript(transcript, style)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes video transcripts clearly and concisely."},
                    {"role": "user", "content": f"{prompt}\n\n{transcript}"}
                ],
                max_tokens=settings.OPENAI_MAX_TOKENS,
                temperature=0.7
            )

            summary = response.choices[0].message.content.strip()
            return summary

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None

    def summarize_long_transcript(self, transcript: str, style: str = None) -> Optional[str]:
        """
        Summarize a long transcript by chunking and combining summaries

        Args:
            transcript: The video transcript text
            style: Summary style

        Returns:
            Combined summary or None if failed
        """
        if not self.client:
            return None

        style = style or settings.SUMMARY_STYLE

        # Split transcript into chunks
        max_chunk_size = 10000
        words = transcript.split()
        chunks = []
        current_chunk = []
        current_size = 0

        for word in words:
            current_chunk.append(word)
            current_size += len(word) + 1

            if current_size >= max_chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_size = 0

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        logger.info(f"Splitting transcript into {len(chunks)} chunks")

        # Summarize each chunk
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that summarizes video transcript segments."},
                        {"role": "user", "content": f"Summarize this part of a video transcript:\n\n{chunk}"}
                    ],
                    max_tokens=500,
                    temperature=0.7
                )

                chunk_summary = response.choices[0].message.content.strip()
                chunk_summaries.append(chunk_summary)
                logger.info(f"Summarized chunk {i+1}/{len(chunks)}")

            except Exception as e:
                logger.error(f"Error summarizing chunk {i+1}: {e}")
                continue

        if not chunk_summaries:
            return None

        # Combine chunk summaries into final summary
        combined_text = '\n\n'.join(chunk_summaries)

        try:
            final_prompt = "Combine the following summaries into a single coherent summary:"
            if style == 'bullet_points':
                final_prompt = "Combine the following summaries into a single list of bullet points:"

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates comprehensive summaries."},
                    {"role": "user", "content": f"{final_prompt}\n\n{combined_text}"}
                ],
                max_tokens=settings.OPENAI_MAX_TOKENS,
                temperature=0.7
            )

            final_summary = response.choices[0].message.content.strip()
            return final_summary

        except Exception as e:
            logger.error(f"Error creating final summary: {e}")
            # Return combined chunk summaries as fallback
            return combined_text

    def generate_title_summary(self, title: str, description: str) -> Optional[str]:
        """
        Generate a brief summary from video title and description (fallback when no transcript)

        Args:
            title: Video title
            description: Video description

        Returns:
            Summary text or None if failed
        """
        if not self.client:
            return None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes video content."},
                    {"role": "user", "content": f"Based on this video title and description, provide a brief summary:\n\nTitle: {title}\n\nDescription: {description}"}
                ],
                max_tokens=300,
                temperature=0.7
            )

            summary = response.choices[0].message.content.strip()
            return summary

        except Exception as e:
            logger.error(f"Error generating title summary: {e}")
            return None
