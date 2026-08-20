from typing import Optional
import logging
import requests
import json

from app.config import settings

logger = logging.getLogger(__name__)


class SummarizerService:
    def __init__(self):
        self.use_openrouter = False
        self.use_deepseek = False
        self.use_openai = False
        self.model = settings.OPENAI_MODEL
        self.api_key = None
        self.base_url = None

        # Priority: OpenRouter > DeepSeek > OpenAI
        if settings.USE_OPENROUTER and settings.OPENROUTER_API_KEY:
            self.use_openrouter = True
            self.api_key = settings.OPENROUTER_API_KEY
            self.base_url = settings.OPENROUTER_BASE_URL
            self.model = settings.OPENROUTER_MODEL
            logger.info(f"Using OpenRouter with model: {self.model}")
        elif settings.USE_DEEPSEEK and settings.DEEPSEEK_API_KEY:
            self.use_deepseek = True
            self.api_key = settings.DEEPSEEK_API_KEY
            self.base_url = settings.DEEPSEEK_BASE_URL
            self.model = settings.DEEPSEEK_MODEL
            logger.info("Using DeepSeek API")
        elif settings.OPENAI_API_KEY:
            self.use_openai = True
            self.api_key = settings.OPENAI_API_KEY
            self.base_url = "https://api.openai.com/v1"
            self.model = settings.OPENAI_MODEL
            logger.info("Using OpenAI API")

    def _make_request(self, prompt: str, max_tokens: int = 1000) -> Optional[str]:
        """Make direct HTTP request to the configured API"""
        if not self.api_key:
            logger.error("No API key configured")
            return None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        if self.use_openrouter:
            headers["HTTP-Referer"] = "https://localhost"
            headers["X-Title"] = "YouTube Crawler"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that summarizes video content clearly and concisely."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        try:
            url = f"{self.base_url}/chat/completions"
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return None

    def summarize_transcript(self, transcript: str, style: str = None) -> Optional[str]:
        if not self.api_key:
            logger.error("No API key configured for summarization")
            return None

        if not transcript or len(transcript.strip()) == 0:
            logger.warning("Empty transcript provided")
            return None

        style = style or settings.SUMMARY_STYLE

        prompts = {
            'concise': "Provide a concise 2-3 sentence summary of the following video transcript:",
            'detailed': "Provide a detailed summary of the following video transcript, including main points and key takeaways:",
            'bullet_points': "Summarize the following video transcript as a list of bullet points covering the main topics:"
        }

        prompt = prompts.get(style, prompts['concise'])

        max_chars = 12000
        if len(transcript) > max_chars:
            return self.summarize_long_transcript(transcript, style)

        full_prompt = f"{prompt}\n\n{transcript}"
        return self._make_request(full_prompt, settings.OPENAI_MAX_TOKENS)

    def summarize_long_transcript(self, transcript: str, style: str = None) -> Optional[str]:
        if not self.api_key:
            return None

        style = style or settings.SUMMARY_STYLE
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

        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            summary = self._make_request(f"Summarize this part of a video transcript:\n\n{chunk}", 500)
            if summary:
                chunk_summaries.append(summary)
                logger.info(f"Summarized chunk {i+1}/{len(chunks)}")

        if not chunk_summaries:
            return None

        combined_text = '\n\n'.join(chunk_summaries)
        final_prompt = "Combine the following summaries into a single coherent summary:"
        if style == 'bullet_points':
            final_prompt = "Combine the following summaries into a single list of bullet points:"

        return self._make_request(f"{final_prompt}\n\n{combined_text}", settings.OPENAI_MAX_TOKENS)

    def generate_title_summary(self, title: str, description: str) -> Optional[str]:
        if not self.api_key:
            return None

        prompt = f"Based on this video title and description, provide a brief summary:\n\nTitle: {title}\n\nDescription: {description or ''}"
        return self._make_request(prompt, 300)
