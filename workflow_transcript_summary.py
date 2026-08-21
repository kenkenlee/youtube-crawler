#!/usr/bin/env python3
"""
YouTube Transcript + AI Summary Workflow

This script demonstrates how to:
1. Fetch a transcript from YouTube
2. Generate an AI summary using your configured provider (OpenRouter/DeepSeek/OpenAI)
3. Save the result

Usage:
    python workflow_transcript_summary.py <video_id> [--style concise|detailed|bullet_points]

Example:
    python workflow_transcript_summary.py dQw4w9wg… --style concise
"""

import sys
import os
from pathlib import Path

# Add project root to path so we can import app services
sys.path.insert(0, str(Path(__file__).parent))

from app.services.transcript_service import TranscriptService
from app.services.summarizer_service import SummarizerService
from app.config import settings


def run_transcript_summary_workflow(video_id: str, style: str = "concise", cookies_file: str = None):
    """
    Complete workflow: fetch transcript → generate AI summary → print result

    Args:
        video_id: YouTube video ID
        style: Summary style (concise / detailed / bullet_points)
        cookies_file: Path to cookies.txt (helps bypass YouTube rate limits)
    """
    print("=" * 70)
    print("🎬 YOUTUBE TRANSCRIPT + AI SUMMARY WORKFLOW")
    print("=" * 70)
    print(f"Video ID: {video_id}")
    print(f"Summary style: {style}")
    if cookies_file:
        print(f"Cookies: {cookies_file}")
    print(f"AI Provider: {'OpenRouter' if settings.USE_OPENROUTER else 'DeepSeek' if settings.USE_DEEPSEEK else 'OpenAI' if settings.OPENAI_API_KEY else 'None (summaries disabled)'}")
    print("-" * 70)

    # Step 1: Fetch transcript
    print("\n📥 Step 1: Fetching transcript...")
    transcript = TranscriptService.get_transcript(video_id, cookies_file=cookies_file)

    if not transcript:
        print("❌ Failed to get transcript. Video may have no captions.")
        return None

    print(f"✅ Transcript fetched ({len(transcript)} characters)")

    # Step 2: Generate AI summary
    print("\n🤖 Step 2: Generating AI summary...")

    summarizer = SummarizerService()

    if not summarizer.api_key:
        print("⚠️  No AI API key configured. Returning raw transcript only.")
        print("\n" + "=" * 70)
        print("RAW TRANSCRIPT (first 1500 chars):")
        print("=" * 70)
        print(transcript[:1500] + ("..." if len(transcript) > 1500 else ""))
        return transcript

    summary = summarizer.summarize_transcript(transcript, style=style)

    if summary:
        print("✅ AI summary generated successfully!")
        print("\n" + "=" * 70)
        print(f"AI SUMMARY ({style.upper()}):")
        print("=" * 70)
        print(summary)
        print("=" * 70)
    else:
        print("❌ Failed to generate summary (check API key / quota)")

    return {
        "video_id": video_id,
        "transcript_length": len(transcript),
        "summary": summary,
        "provider": summarizer.model
    }


def batch_workflow(video_ids: list, style: str = "concise", cookies_file: str = None):
    """Process multiple videos in batch."""
    results = []
    for i, vid in enumerate(video_ids, 1):
        print(f"\n{'='*70}")
        print(f"Processing video {i}/{len(video_ids)}: {vid}")
        if cookies_file:
            print(f"Using cookies: {cookies_file}")
        print(f"{'='*70}")
        result = run_transcript_summary_workflow(vid, style, cookies_file=cookies_file)
        results.append(result)
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python workflow_transcript_summary.py <video_id> [--style concise|detailed|bullet_points]")
        print("\nExamples:")
        print("  python workflow_transcript_summary.py dQw4w9wg…")
        print("  python workflow_transcript_summary.py dQw4w9wg… --style bullet_points")
        sys.exit(1)

    video_id = sys.argv[1]
    style = "concise"

    # Parse optional style argument
    if "--style" in sys.argv:
        idx = sys.argv.index("--style")
        if idx + 1 < len(sys.argv):
            style = sys.argv[idx + 1]

    run_transcript_summary_workflow(video_id, style)