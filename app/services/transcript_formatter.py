"""Transcript formatting utilities (feature 7).

Raw YouTube transcripts are one long stream of lowercase-ish caption text with
no punctuation or layout. This module turns that stream into readable text:
sentences start with a capital letter, punctuation is tidied up, and text is
laid out in paragraphs of reasonable length.
"""
import re
from typing import List


# Common words that should NOT trigger a mid-sentence capital unless they start
# a sentence. Keep this list small — it is a heuristic, not a grammar checker.
_LOWER_KEEP = {
    "a", "an", "and", "as", "at", "but", "by", "for", "in", "into", "is", "it",
    "of", "on", "or", "so", "the", "to", "with", "yet", "i",
}
_PROPER_NOUNS = {
    "i", "i'm", "i've", "i'll", "i'd", "youtube", "google", "ai", "llm", "gpt",
    "openai", "microsoft", "apple", "google", "python", "javascript", "hkpc",
}
_SENTENCE_END = re.compile(r"[.!?](\s|$)")


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences on ., !, ? followed by whitespace/end."""
    parts = _SENTENCE_END.split(text)
    # Re-attach the ending punctuation that split() removed
    sentences = []
    idx = 0
    for match in _SENTENCE_END.finditer(text):
        end = match.end()
        fragment = text[idx:end]
        # Strip the trailing whitespace that belonged to the next sentence
        fragment = fragment.rstrip()
        if fragment:
            sentences.append(fragment)
        idx = end
    if idx < len(text):
        tail = text[idx:].strip()
        if tail:
            sentences.append(tail)
    return [s for s in sentences if s.strip()]


def _capitalize_sentence(sentence: str) -> str:
    """Capitalize the first letter of a sentence, preserving other casing."""
    s = sentence.strip()
    if not s:
        return s
    # Find first alphabetic character
    for i, ch in enumerate(s):
        if ch.isalpha():
            return s[:i] + ch.upper() + s[i + 1:]
    return s


def _fix_i(text: str) -> str:
    """Ensure standalone 'i' is capitalized."""
    return re.sub(r"\bi\b", "I", text)


def format_transcript(raw: str, sentences_per_paragraph: int = 4) -> str:
    """Format a raw transcript into readable text.

    - Ensures every sentence starts with a capital letter.
    - Capitalizes standalone "i" and common proper nouns.
    - Splits the stream into sentences and lays them out in paragraphs.
    - Keeps existing punctuation; only tidies whitespace.
    """
    if not raw:
        return raw

    text = raw.replace("\r\n", " ").replace("\n", " ")
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return text

    sentences = _split_sentences(text)
    if not sentences:
        return _capitalize_sentence(text)

    formatted_sentences = []
    for sentence in sentences:
        s = _capitalize_sentence(sentence)
        s = _fix_i(s)
        # Capitalize known proper nouns anywhere in the sentence (word boundary)
        for noun, replacement in (
            ("youtube", "YouTube"), ("google", "Google"), ("ai", "AI"),
            ("llm", "LLM"), ("gpt", "GPT"), ("openai", "OpenAI"),
            ("python", "Python"), ("javascript", "JavaScript"), ("hkpc", "HKPC"),
        ):
            s = re.sub(rf"\b{re.escape(noun)}\b", replacement, s, flags=re.IGNORECASE)
        formatted_sentences.append(s)

    # Group sentences into paragraphs
    paragraphs = []
    for i in range(0, len(formatted_sentences), sentences_per_paragraph):
        paragraphs.append(" ".join(formatted_sentences[i:i + sentences_per_paragraph]))

    return "\n\n".join(paragraphs)


def format_transcript_segments(segments: List[dict], sentences_per_paragraph: int = 4) -> str:
    """Format a list of transcript segments (dicts with 'text' key) into readable text."""
    raw_text = " ".join(seg.get("text", "") for seg in segments)
    return format_transcript(raw_text, sentences_per_paragraph)
