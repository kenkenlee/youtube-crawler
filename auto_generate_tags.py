"""
Auto-generate tags for videos without tags
Extracts keywords from title, description, and summary
"""
import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.video import Video
import re
from collections import Counter

def extract_keywords(text, min_length=3, max_keywords=10):
    """Extract meaningful keywords from text"""
    if not text:
        return []
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters but keep spaces and hyphens
    text = re.sub(r'[^\w\s-]', ' ', text)
    
    # Split into words
    words = text.split()
    
    # Common stop words to exclude
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these',
        'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which',
        'who', 'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
        'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
        'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'about'
    }
    
    # Filter words
    keywords = []
    for word in words:
        # Skip if too short, is stop word, or is number only
        if len(word) >= min_length and word not in stop_words and not word.isdigit():
            keywords.append(word)
    
    # Count frequency
    word_freq = Counter(keywords)
    
    # Get most common words
    common_words = [word for word, count in word_freq.most_common(max_keywords)]
    
    return common_words

def generate_tags_for_video(video):
    """Generate tags from video content"""
    all_keywords = []
    
    # Extract from title (most important)
    if video.title:
        title_keywords = extract_keywords(video.title, min_length=3, max_keywords=5)
        all_keywords.extend(title_keywords)
    
    # Extract from description
    if video.description:
        desc_keywords = extract_keywords(video.description, min_length=4, max_keywords=5)
        all_keywords.extend(desc_keywords)
    
    # Extract from summary
    if video.summary_text:
        summary_keywords = extract_keywords(video.summary_text, min_length=4, max_keywords=5)
        all_keywords.extend(summary_keywords)
    
    # Add channel name as tag
    if video.channel and video.channel.channel_name:
        channel_words = extract_keywords(video.channel.channel_name, min_length=3, max_keywords=2)
        all_keywords.extend(channel_words)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for keyword in all_keywords:
        if keyword not in seen:
            seen.add(keyword)
            unique_tags.append(keyword)
    
    # Limit to 15 tags
    return unique_tags[:15]

db = SessionLocal()

try:
    # Find videos with empty tags
    videos_without_tags = db.query(Video).filter(
        (Video.tags == None) | (Video.tags == '[]')
    ).all()
    
    print(f'Found {len(videos_without_tags)} videos without tags')
    print('Auto-generating tags from content...')
    print()
    
    updated_count = 0
    
    for i, video in enumerate(videos_without_tags, 1):
        try:
            print(f'[{i}/{len(videos_without_tags)}] Processing: {video.title[:60]}...')
            
            # Generate tags
            generated_tags = generate_tags_for_video(video)
            
            if generated_tags:
                video.tags = generated_tags
                updated_count += 1
                print(f'  [OK] Generated {len(generated_tags)} tags: {generated_tags[:5]}...')
            else:
                print(f'  [SKIP] Could not generate tags')
                video.tags = []
                
        except Exception as e:
            print(f'  [ERROR] {str(e)[:80]}')
            if video.tags is None:
                video.tags = []
    
    # Commit all changes
    db.commit()
    
    print()
    print('='*60)
    print(f'[SUCCESS] Tag generation complete!')
    print(f'  Updated: {updated_count} videos')
    print(f'  Failed: {len(videos_without_tags) - updated_count} videos')
    print('='*60)
    
except Exception as e:
    db.rollback()
    print(f'[ERROR] Update failed: {e}')
    import traceback
    traceback.print_exc()
finally:
    db.close()
