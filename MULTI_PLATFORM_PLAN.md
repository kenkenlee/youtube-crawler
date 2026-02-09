# Multi-Platform Support Implementation Plan

## Overview
Add support for X.com (Twitter) and Instagram channels alongside YouTube.

---

## Phase 1: Database Schema Updates

### 1.1 Add Platform Field to Channels Table
```sql
ALTER TABLE channels ADD COLUMN platform VARCHAR(50) DEFAULT 'youtube';
-- Values: 'youtube', 'twitter', 'instagram'
```

### 1.2 Update Channel Model
- Add `platform` field (youtube/twitter/instagram)
- Add `platform_specific_data` JSON field for platform-specific metadata

### 1.3 Update Video Model
- Add `platform` field
- Add `platform_post_id` (tweet_id, instagram_post_id, etc.)
- Rename `video_url` to `content_url` (more generic)

---

## Phase 2: API Integration

### 2.1 Twitter/X.com API
**Requirements:**
- Twitter API v2 credentials
- Bearer token or OAuth 2.0

**Endpoints Needed:**
- Get user timeline
- Get tweet details
- Get user info

**Python Libraries:**
- `tweepy` (official Twitter API library)
- `python-twitter` (alternative)

### 2.2 Instagram API
**Requirements:**
- Instagram Basic Display API or Graph API
- Facebook Developer account
- Access token

**Endpoints Needed:**
- Get user media
- Get media details
- Get user info

**Python Libraries:**
- `instagrapi` (unofficial, more features)
- `instagram-private-api` (alternative)
- Official Instagram Graph API (limited)

---

## Phase 3: UI Updates

### 3.1 Add Channel Form
**Changes:**
- Add platform selector dropdown (YouTube/Twitter/Instagram)
- Dynamic URL placeholder based on platform
- Platform-specific validation

**Example:**
```
Platform: [YouTube ▼]
URL: https://www.youtube.com/@channelname

Platform: [Twitter ▼]
URL: https://twitter.com/username

Platform: [Instagram ▼]
URL: https://instagram.com/username
```

### 3.2 Channel List
- Show platform icon/badge for each channel
- Filter by platform
- Platform-specific actions

### 3.3 Videos/Posts List
- Rename "Videos" to "Content" or "Posts"
- Show platform-specific metadata
- Platform icons

---

## Phase 4: Crawler Service Updates

### 4.1 Create Platform-Specific Services
```
app/services/
├── youtube_service.py (existing)
├── twitter_service.py (new)
├── instagram_service.py (new)
└── platform_factory.py (new - factory pattern)
```

### 4.2 Unified Crawler Interface
```python
class PlatformCrawler(ABC):
    @abstractmethod
    def get_channel_info(self, url):
        pass
    
    @abstractmethod
    def get_posts(self, channel_id, max_results):
        pass
    
    @abstractmethod
    def get_post_details(self, post_id):
        pass
```

---

## Phase 5: Configuration

### 5.1 Environment Variables
```env
# Twitter/X.com API
TWITTER_API_KEY=your-api-key
TWITTER_API_SECRET=your-api-secret
TWITTER_BEARER_TOKEN=your-bearer-token

# Instagram API
INSTAGRAM_ACCESS_TOKEN=your-access-token
INSTAGRAM_CLIENT_ID=your-client-id
INSTAGRAM_CLIENT_SECRET=your-client-secret
```

### 5.2 Feature Flags
```env
ENABLE_TWITTER=True
ENABLE_INSTAGRAM=True
ENABLE_YOUTUBE=True
```

---

## Phase 6: Implementation Steps

### Step 1: Database Migration (30 min)
- [ ] Add platform column to channels
- [ ] Add platform column to videos
- [ ] Add platform_specific_data JSON column
- [ ] Migrate existing data (set platform='youtube')

### Step 2: Install Dependencies (10 min)
```bash
pip install tweepy instagrapi
```

### Step 3: Create Twitter Service (2 hours)
- [ ] Create twitter_service.py
- [ ] Implement authentication
- [ ] Implement get_user_info()
- [ ] Implement get_tweets()
- [ ] Implement get_tweet_details()

### Step 4: Create Instagram Service (2 hours)
- [ ] Create instagram_service.py
- [ ] Implement authentication
- [ ] Implement get_user_info()
- [ ] Implement get_posts()
- [ ] Implement get_post_details()

### Step 5: Update UI (1 hour)
- [ ] Add platform selector to add channel form
- [ ] Update channel list to show platform icons
- [ ] Update videos page (rename to "Content")
- [ ] Add platform filters

### Step 6: Update Crawler (1 hour)
- [ ] Create platform factory
- [ ] Update crawler_service.py to use factory
- [ ] Handle platform-specific logic

### Step 7: Testing (1 hour)
- [ ] Test Twitter channel addition
- [ ] Test Instagram channel addition
- [ ] Test crawling from each platform
- [ ] Test mixed platform crawls

**Total Estimated Time: 7-8 hours**

---

## Challenges & Considerations

### 1. API Rate Limits
- **Twitter:** 300 requests per 15 min (free tier)
- **Instagram:** Varies by endpoint
- **Solution:** Implement rate limiting and caching

### 2. Authentication Complexity
- Twitter requires OAuth or Bearer token
- Instagram requires Facebook app setup
- **Solution:** Detailed setup documentation

### 3. Content Differences
- YouTube: Videos with transcripts
- Twitter: Short text posts (tweets)
- Instagram: Images/videos with captions
- **Solution:** Flexible content model

### 4. Summarization
- YouTube: Summarize transcripts
- Twitter: Summarize thread or single tweet
- Instagram: Summarize caption + image description
- **Solution:** Platform-aware summarization

---

## Alternative: Simplified Approach

### Quick Implementation (2-3 hours)
Instead of full API integration, start with:

1. **URL Storage Only**
   - Allow adding Twitter/Instagram URLs
   - Store as reference links
   - No automatic crawling yet

2. **Manual Content Addition**
   - Add posts manually via URL
   - Fetch basic metadata
   - Store for reference

3. **Future Enhancement**
   - Add full API integration later
   - Incremental feature rollout

---

## Recommendation

**Option A: Full Implementation** (7-8 hours)
- Complete multi-platform support
- Automatic crawling
- Full feature parity

**Option B: Simplified Version** (2-3 hours)
- Basic URL storage
- Manual content addition
- Upgrade path for future

**Which approach would you prefer?**

---

## Next Steps

1. Choose implementation approach
2. Set up API credentials (Twitter, Instagram)
3. Run database migrations
4. Implement platform services
5. Update UI
6. Test and deploy

---

**Note:** Twitter API requires approval and Instagram API requires Facebook Developer account. Setup time not included in estimates.
