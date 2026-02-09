"""
Fetch transcripts for all videos with rate limiting to avoid IP ban
"""
import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.video import Video
from app.services.transcript_service import TranscriptService
import time
import random

db = SessionLocal()
transcript_service = TranscriptService()

try:
    # Find videos without transcripts
    videos_without_transcript = db.query(Video).filter(
        (Video.transcript_text == None) | (Video.transcript_text == '')
    ).all()
    
    print(f'Found {len(videos_without_transcript)} videos without transcripts')
    print('Fetching transcripts with rate limiting...')
    print('(This will take a while to avoid YouTube blocking)')
    print()
    
    success_count = 0
    failed_count = 0
    
    for i, video in enumerate(videos_without_transcript, 1):
        try:
            print(f'[{i}/{len(videos_without_transcript)}] Video ID: {video.video_id}')
            
            # Fetch transcript
            transcript = transcript_service.get_transcript(video.video_id)
            
            if transcript:
                video.transcript_text = transcript
                success_count += 1
                print(f'  [OK] Transcript fetched ({len(transcript)} chars)')
            else:
                failed_count += 1
                print(f'  [SKIP] No transcript available')
            
            # Commit every 5 videos
            if i % 5 == 0:
                db.commit()
                print(f'  [SAVED] Progress saved')
            
            # Rate limiting: wait 2-4 seconds between requests
            if i < len(videos_without_transcript):
                delay = random.uniform(2, 4)
                print(f'  [WAIT] Sleeping {delay:.1f}s to avoid rate limit...')
                time.sleep(delay)
                
        except Exception as e:
            failed_count += 1
            error_msg = str(e)
            if 'blocked' in error_msg.lower() or 'too many' in error_msg.lower():
                print(f'  [ERROR] Rate limited! Waiting 30 seconds...')
                time.sleep(30)
            else:
                print(f'  [ERROR] {error_msg[:80]}')
    
    # Final commit
    db.commit()
    
    print()
    print('='*60)
    print(f'[SUCCESS] Transcript fetching complete!')
    print(f'  Success: {success_count} videos')
    print(f'  Failed/No transcript: {failed_count} videos')
    print('='*60)
    
except Exception as e:
    db.rollback()
    print(f'[ERROR] Update failed: {e}')
finally:
    db.close()
