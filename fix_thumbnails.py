import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.channel import Channel
import yt_dlp

db = SessionLocal()

try:
    channels = db.query(Channel).all()
    print(f'Found {len(channels)} channels to update\n')
    
    updated = 0
    for channel in channels:
        print(f'Channel {channel.id}: {channel.channel_name[:40]}')
        
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(channel.channel_url, download=False)
                
                if info:
                    # Get thumbnail
                    thumbnail = info.get('thumbnail') or info.get('thumbnails', [{}])[0].get('url', '')
                    
                    # Get channel ID
                    yt_channel_id = info.get('channel_id') or info.get('uploader_id')
                    
                    if thumbnail:
                        channel.thumbnail_url = thumbnail
                        print(f'  [OK] Thumbnail: {thumbnail[:60]}...')
                        updated += 1
                    else:
                        print(f'  [SKIP] No thumbnail found')
                    
                    if yt_channel_id and not channel.youtube_channel_id:
                        channel.youtube_channel_id = yt_channel_id
                        print(f'  [OK] YouTube ID: {yt_channel_id}')
                else:
                    print(f'  [ERROR] Could not fetch channel info')
                    
        except Exception as e:
            print(f'  [ERROR] {str(e)[:80]}')
        
        print()
    
    db.commit()
    print(f'\n{"="*60}')
    print(f'SUCCESS: Updated {updated}/{len(channels)} channels')
    print(f'{"="*60}')
    
except Exception as e:
    db.rollback()
    print(f'\nFATAL ERROR: {e}')
finally:
    db.close()
