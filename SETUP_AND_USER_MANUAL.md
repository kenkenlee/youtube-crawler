# YouTube Channel Crawler - Complete Setup & User Manual

**Version:** 2.0 (OpenRouter + DeepSeek Edition)
**Last Updated:** 2026-08-21

---

## Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the Application](#running-the-application)
6. [Web Interface Guide](#web-interface-guide)
7. [API Reference](#api-reference)
8. [Troubleshooting](#troubleshooting)
9. [Advanced Topics](#advanced-topics)

---

## Overview

The YouTube Channel Crawler is a full-featured web application that:

- Crawls YouTube channels automatically
- Extracts video metadata, transcripts, and thumbnails
- Generates **AI-powered summaries** using OpenRouter, DeepSeek, or OpenAI
- Provides a modern web dashboard for management
- Supports scheduled recurring crawls
- Exports data to Excel/CSV

**Key Highlights:**
- ✅ Works globally (no regional OpenAI blocks)
- ✅ Uses **OpenRouter + DeepSeek** by default (cheap & reliable)
- ✅ No YouTube API key required (uses yt-dlp)
- ✅ Real-time crawl progress via WebSocket
- ✅ Modern Bootstrap 5 UI

---

## System Requirements

| Component       | Requirement          | Notes                              |
|-----------------|----------------------|------------------------------------|
| Python          | 3.8+                 | Tested on 3.13                     |
| pip             | Latest               | Package manager                    |
| Git             | Any recent version   | For cloning                        |
| RAM             | 2 GB minimum         | 4 GB+ recommended for many videos  |
| Disk            | 500 MB+              | Depends on number of videos        |
| Internet        | Required             | For crawling and AI summarization  |

**Optional but Recommended:**
- YouTube Data API key (for faster metadata)
- OpenRouter / DeepSeek / OpenAI API key (for AI summaries)

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/kenkenlee/youtube-crawler.git
cd youtube-crawler
```

### Step 2: Create Virtual Environment (Recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- FastAPI + Uvicorn (web server)
- yt-dlp (YouTube downloader)
- OpenAI client (for OpenRouter/DeepSeek/OpenAI)
- APScheduler (scheduling)
- pandas + openpyxl (exports)
- SQLite (database)

### Step 4: Configure Environment

Copy the example configuration:

```bash
cp .env.example .env
```

Edit `.env` with your preferred settings (see [Configuration](#configuration) section).

---

## Configuration

### Environment Variables (`.env`)

```env
# === Application ===
APP_NAME=YouTube Crawler
DEBUG=True
SECRET_KEY=change-this-to-a-random-string

# === Database ===
DATABASE_URL=sqlite:///./data/database.db

# === YouTube API (Optional) ===
YOUTUBE_API_KEY=your_youtube_api_key_here

# === AI Summarization Provider ===
# Priority: OpenRouter > DeepSeek > OpenAI

# Option 1: OpenRouter (Recommended)
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxxxxxx
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=deepseek/deepseek-chat
USE_OPENROUTER=True

# Option 2: DeepSeek Direct
# DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
# DEEPSEEK_BASE_URL=https://api.deepseek.com
# DEEPSEEK_MODEL=deepseek-chat
# USE_DEEPSEEK=True

# Option 3: OpenAI
# OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
# OPENAI_MODEL=gpt-4
# USE_OPENAI=True

# === Crawler Settings ===
MAX_VIDEOS_PER_CHANNEL=30
AUTO_SUMMARIZE=True
ENABLE_SCHEDULER=True
```

### Recommended Setup (OpenRouter + DeepSeek)

1. Go to [OpenRouter](https://openrouter.ai/keys)
2. Create an account and generate an API key
3. Add the key to `.env`:
   ```env
   OPENROUTER_API_KEY=sk-or-xxxxx
   USE_OPENROUTER=True
   AUTO_SUMMARIZE=True
   ```

---

## Running the Application

### Start the Server

```bash
python run.py
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:5000
INFO:     Application startup complete.
```

### Access the Web UI

| Page          | URL                                      |
|---------------|------------------------------------------|
| Dashboard     | http://127.0.0.1:5000/dashboard          |
| Channels      | http://127.0.0.1:5000/channels           |
| Videos        | http://127.0.0.1:5000/videos             |
| API Docs      | http://127.0.0.1:5000/docs               |

---

## Web Interface Guide

### 1. Adding a Channel

1. Go to **Channels** page
2. Click **Add Channel**
3. Fill in:
   - **Reference ID**: Unique slug (e.g., `mkbhd`)
   - **Channel Name**: Display name (e.g., `MKBHD`)
   - **YouTube URL**: Any valid channel URL
   - **Keywords**: Optional tags
4. Click **Add Channel**

**Supported URL formats:**
- `https://www.youtube.com/@mkbhd`
- `https://www.youtube.com/channel/UC...`
- `https://www.youtube.com/c/MKBHD`

### 2. Starting a Crawl

1. Go to **Dashboard**
2. Click **Start New Crawl**
3. Select channels
4. (Optional) Add filter keywords
5. Click **Start Crawl**
6. Watch real-time progress

### 3. Viewing Videos & Summaries

- Go to **Videos** page
- Click any video row to expand
- AI summaries appear automatically (if configured)

### 4. Exporting Data

- Go to **Dashboard → Export**
- Choose format: Excel (.xlsx) or CSV
- Filter by date range or keywords

---

## API Reference

### Authentication

No authentication required for local use.

### Endpoints

| Method | Endpoint                    | Description                     |
|--------|-----------------------------|---------------------------------|
| GET    | `/channels`                 | List all channels               |
| POST   | `/channels`                 | Add new channel                 |
| GET    | `/videos`                   | List videos (with filters)      |
| POST   | `/crawl/start`              | Start a new crawl session       |
| GET    | `/crawl/status/{session_id}`| Get crawl progress              |
| GET    | `/export/videos`            | Export videos to Excel/CSV      |

Full interactive docs: http://127.0.0.1:5000/docs

---

## Troubleshooting

### Common Issues

**"Could not extract channel ID"**
- This error no longer occurs (validation removed in v2.0)
- Just use any valid YouTube channel URL

**AI summaries not appearing**
- Check that `AUTO_SUMMARIZE=True` in `.env`
- Verify your OpenRouter/DeepSeek/OpenAI key is valid
- Check logs for API errors

**Crawl is slow**
- Reduce `MAX_VIDEOS_PER_CHANNEL`
- Add a YouTube API key for faster metadata

**Database locked / corrupted**
```bash
rm data/database.db
python run.py   # will recreate
```

---

## Advanced Topics

### Scheduled Crawls

Edit `.env`:
```env
ENABLE_SCHEDULER=True
DAILY_CRAWL_TIME=02:00
```

The scheduler runs automatically when the server starts.

### Using Multiple AI Providers

You can switch providers anytime by changing `.env` and restarting the server.

### Docker Deployment

```bash
docker-compose up -d
```

(See `docker-compose.yml` for details)

---

## License

MIT License — see `LICENSE` file.

## Support

- GitHub Issues: https://github.com/kenkenlee/youtube-crawler/issues
- Documentation: See `README.md` and `FINAL_STATUS.md`

---

**Enjoy crawling!** 🦞