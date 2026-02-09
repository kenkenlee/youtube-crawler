"""
Fetch transcripts for all videos missing transcripts
"""
import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.video import Video
from app.services.transcript_service import TranscriptService

db = SessionLocal()
transcript_service = TranscriptService()

try:
    # Find videos without transcripts
    videos_without_transcript = db.query(Video).filter(
        (Video.transcript_text == None) | (Video.transcript_text == '')
    ).all()
    
    print(f'Found {len(videos_without_transcript)} videos without transcripts')
    print('Fetching transcripts...')
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
                
            # Commit every 10 videos to avoid losing progress
            if i % 10 == 0:
                db.commit()
                print(f'  [SAVED] Progress saved ({i} videos processed)')
                
        except Exception as e:
            failed_count += 1
            print(f'  [ERROR] {str(e)[:80]}')
    
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
    import traceback
    traceback.print_exc()
finally:
    db.close()
