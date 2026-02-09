"""
Fix videos with missing tags using yt-dlp
"""
import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.video import Video
import yt_dlp

db = SessionLocal()

try:
    # Find videos with empty tags
    videos_without_tags = db.query(Video).filter(
        (Video.tags == None) | (Video.tags == '[]')
    ).all()
    
    print(f'Found {len(videos_without_tags)} videos with missing tags')
    print('Fetching tags using yt-dlp...')
    print()
    
    updated_count = 0
    no_tags_count = 0
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    for i, video in enumerate(videos_without_tags, 1):
        try:
            print(f'[{i}/{len(videos_without_tags)}] Video ID: {video.video_id}')
            
            url = f'https://www.youtube.com/watch?v={video.video_id}'
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info and info.get('tags'):
                    video.tags = info['tags']
                    updated_count += 1
                    print(f'  [OK] Added {len(info["tags"])} tags')
                else:
                    # Set to empty list to mark as checked
                    video.tags = []
                    no_tags_count += 1
                    print(f'  [SKIP] No tags available')
                    
        except Exception as e:
            print(f'  [ERROR] {str(e)[:80]}')
            # Set to empty list to mark as checked
            if video.tags is None:
                video.tags = []
            no_tags_count += 1
    
    # Commit all changes
    db.commit()
    
    print()
    print('='*60)
    print(f'[SUCCESS] Tag update complete!')
    print(f'  Updated: {updated_count} videos')
    print(f'  No tags available: {no_tags_count} videos')
    print('='*60)
    
except Exception as e:
    db.rollback()
    print(f'[ERROR] Update failed: {e}')
finally:
    db.close()
