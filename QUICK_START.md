# YouTube Channel Crawler - Quick Start Guide

## 🎉 Application Successfully Running!

**Access URL**: http://127.0.0.1:5000

### Quick Links
- **Dashboard**: http://127.0.0.1:5000/dashboard
- **Channels**: http://127.0.0.1:5000/channels
- **Videos**: http://127.0.0.1:5000/videos
- **Sessions**: http://127.0.0.1:5000/sessions
- **API Docs**: http://127.0.0.1:5000/docs

---

## 🚀 Getting Started in 3 Steps

### Step 1: Configure API Keys (Optional but Recommended)

Edit `.env` file and add your API keys:

```bash
# Get from: https://console.cloud.google.com/
YOUTUBE_API_KEY=your-youtube-api-key

# Get from: https://platform.openai.com/api-keys
OPENAI_API_KEY=your-openai-api-key
```

**Note**: The app works without API keys but with limitations:
- Without YouTube API: Uses yt-dlp (slower but functional)
- Without OpenAI API: Cannot generate AI summaries

### Step 2: Add Your First Channel

1. Open http://127.0.0.1:5000/channels
2. Click **"Add Channel"**
3. Enter a YouTube channel URL, for example:
   - `https://www.youtube.com/@mkbhd` (Tech reviews)
   - `https://www.youtube.com/@veritasium` (Science)
   - `https://www.youtube.com/@3blue1brown` (Math)
4. Add keywords (optional): `tutorial, review, guide`
5. Click **"Add Channel"**

### Step 3: Start Your First Crawl

1. Go to http://127.0.0.1:5000/dashboard
2. Click **"Start New Crawl"**
3. Select the channel(s) you added
4. Add filter keywords (optional): `AI, machine learning`
5. Click **"Start Crawl"**
6. Watch real-time progress!

---

## 📋 Features Overview

### ✅ What You Can Do

1. **Channel Management**
   - Add unlimited YouTube channels
   - Set keywords for automatic filtering
   - Enable/disable crawling per channel
   - Schedule automatic daily/weekly crawls

2. **Video Discovery**
   - Automatically fetch videos from channels
   - Filter by keywords (title, description, tags)
   - Extract metadata (views, likes, duration, etc.)
   - Track matched keywords per video

3. **AI Summarization**
   - Extract video transcripts automatically
   - Generate AI summaries using GPT-4
   - Handle long videos (automatic chunking)
   - Regenerate summaries on demand

4. **Session Monitoring**
   - Real-time progress tracking
   - WebSocket live updates
   - Error logging and reporting
   - Session history and statistics

5. **Search & Browse**
   - Search videos by keywords
   - Filter by channel, summary status
   - View detailed video information
   - Watch videos directly (embedded player)

6. **Automation**
   - Schedule daily/weekly crawls
   - Auto-summarize new videos
   - Daily completion reports
   - Background task processing

---

## 🎯 Example Workflows

### Workflow 1: Monitor Tech Channels

1. Add channels: MKBHD, Linus Tech Tips, Dave2D
2. Set keywords: `review, smartphone, laptop`
3. Enable daily crawling
4. Get AI summaries of all tech reviews automatically

### Workflow 2: Research Specific Topics

1. Add educational channels
2. Create manual session with keywords: `AI, neural networks`
3. Only videos matching keywords are processed
4. Read AI summaries to quickly understand content

### Workflow 3: Content Curation

1. Add multiple channels in your niche
2. Set specific keywords for filtering
3. Browse summarized videos
4. Export data for further analysis

---

## 🔧 Configuration Options

Edit `.env` to customize:

```bash
# Crawler Settings
MAX_VIDEOS_PER_CHANNEL=50        # Videos to fetch per channel
CRAWL_DELAY_SECONDS=1            # Delay between requests

# Summarization
AUTO_SUMMARIZE=True              # Auto-generate summaries
SUMMARY_STYLE=concise            # concise/detailed/bullet_points
OPENAI_MODEL=gpt-4               # OpenAI model
OPENAI_MAX_TOKENS=1000           # Max summary length

# Scheduler
ENABLE_SCHEDULER=True            # Enable background tasks
DAILY_CRAWL_TIME=02:00          # Daily crawl time (24h)
```

---

## 📊 API Examples

### Using curl (if available)

```bash
# List all channels
curl http://127.0.0.1:5000/api/channels

# Get dashboard statistics
curl http://127.0.0.1:5000/api/dashboard/stats

# Search videos
curl "http://127.0.0.1:5000/api/videos/search?q=tutorial"

# Create crawl session
curl -X POST http://127.0.0.1:5000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "My First Crawl",
    "session_type": "manual",
    "channel_ids": [1],
    "filter_keywords": ["AI", "tutorial"]
  }'
```

### Using Python

```python
import requests

BASE_URL = "http://127.0.0.1:5000"

# Add a channel
response = requests.post(f"{BASE_URL}/api/channels", json={
    "channel_id": "UCBJycsmduvYEL83R_U4JriQ",
    "channel_name": "MKBHD",
    "channel_url": "https://www.youtube.com/@mkbhd",
    "keywords": ["tech", "review"],
    "crawl_enabled": True,
    "crawl_frequency": "daily"
})

print(response.json())

# Start a crawl session
response = requests.post(f"{BASE_URL}/api/sessions", json={
    "session_name": "Tech Review Crawl",
    "session_type": "manual",
    "channel_ids": [1],
    "filter_keywords": ["smartphone", "laptop"]
})

print(response.json())
```

---

## 🐛 Troubleshooting

### Server Not Starting
- Check if port 5000 is available
- Look for errors in console output
- Verify Python dependencies are installed

### No Videos Found
- Check YouTube channel URL is correct
- Verify channel has public videos
- Check API key if using YouTube API

### Transcripts Not Available
- Not all videos have transcripts
- Some creators disable transcripts
- App will use title/description as fallback

### Summarization Fails
- Verify OpenAI API key is valid
- Check API credits/quota
- Review error logs in session details

### Database Issues
- Database is auto-created on first run
- Located at: `data/database.db`
- Delete and restart to reset

---

## 📁 Project Structure

```
youtube-crawler/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration
│   ├── database.py             # Database setup
│   ├── models/                 # Database models
│   ├── schemas/                # API schemas
│   ├── api/                    # API endpoints
│   ├── services/               # Business logic
│   ├── tasks/                  # Background tasks
│   └── templates/              # HTML templates
├── static/                     # CSS & JavaScript
├── data/                       # Database & logs
├── .env                        # Configuration
├── requirements.txt            # Dependencies
└── run.py                      # Application runner
```

---

## 🎓 Tips & Best Practices

1. **Start Small**: Add 1-2 channels first to test
2. **Use Keywords**: Filter videos to reduce processing time
3. **Monitor Sessions**: Check for errors in session details
4. **API Quotas**: YouTube API has daily limits (10,000 units)
5. **OpenAI Costs**: Each summary costs ~$0.01-0.05
6. **Database Backup**: Backup `data/database.db` regularly

---

## 🚀 Next Steps

1. **Add API Keys**: Configure YouTube and OpenAI APIs
2. **Add Channels**: Start with your favorite channels
3. **Test Crawl**: Run a manual crawl session
4. **Review Results**: Check videos and summaries
5. **Schedule**: Enable daily crawls for automation

---

## 📞 Support

- **API Documentation**: http://127.0.0.1:5000/docs
- **ReDoc**: http://127.0.0.1:5000/redoc
- **GitHub Issues**: (add your repo URL)

---

**Enjoy your YouTube Channel Crawler!** 🎬

The application is running and ready to use at: **http://127.0.0.1:5000**
