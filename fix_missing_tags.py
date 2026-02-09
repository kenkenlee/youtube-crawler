"""
Fix videos with missing tags by fetching from YouTube
"""
import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.video import Video
from app.services.youtube_service import YouTubeService

db = SessionLocal()
youtube_service = YouTubeService()

try:
    # Find videos with empty tags
    videos_without_tags = db.query(Video).filter(
        (Video.tags == None) | (Video.tags == '[]')
    ).all()
    
    print(f'Found {len(videos_without_tags)} videos with missing tags')
    print('Fetching tags from YouTube...')
    print()
    
    updated_count = 0
    failed_count = 0
    
    for video in videos_without_tags:
        try:
            print(f'Processing video {video.id}: {video.title[:50]}...')
            
            # Fetch video details from YouTube
            video_details = youtube_service.get_video_details(video.video_id)
            
            if video_details and video_details.get('tags'):
                video.tags = video_details['tags']
                updated_count += 1
                print(f'  [OK] Added {len(video_details["tags"])} tags')
            else:
                print(f'  [SKIP] No tags available from YouTube')
                # Set to empty list to mark as checked
                if video.tags is None:
                    video.tags = []
                failed_count += 1
                
        except Exception as e:
            print(f'  [ERROR] {str(e)[:50]}')
            failed_count += 1
    
    # Commit all changes
    db.commit()
    
    print()
    print('='*60)
    print(f'[SUCCESS] Tag update complete!')
    print(f'  Updated: {updated_count} videos')
    print(f'  Failed/No tags: {failed_count} videos')
    print('='*60)
    
except Exception as e:
    db.rollback()
    print(f'[ERROR] Update failed: {e}')
finally:
    db.close()
