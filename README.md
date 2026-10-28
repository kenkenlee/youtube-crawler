# YouTube Channel Crawler

A comprehensive YouTube channel crawler with video summarization capabilities, web interface for management, and automated crawling sessions with progress monitoring.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- 📺 **YouTube Channel Management** - Add and manage multiple YouTube channels
- 🤖 **AI-Powered Summarization** - Generate video summaries using OpenAI GPT-4 or DeepSeek
- 🔍 **Smart Filtering** - Filter videos by keywords and topics
- 📊 **Real-time Monitoring** - Track crawl progress with WebSocket updates
- ⏰ **Automated Scheduling** - Schedule regular crawls with APScheduler
- 📈 **Analytics Dashboard** - View statistics and insights
- 📤 **Data Export** - Export to Excel/CSV formats
- 🌐 **Modern Web UI** - Clean, responsive interface with Bootstrap 5
- 🌍 **Region Support** - Works globally with DeepSeek API alternative

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/kenkenlee/youtube-crawler.git
cd youtube-crawler
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**

Copy the `.env` file and update with your API keys:

```bash
# Application
APP_NAME=YouTube Crawler
DEBUG=True

# Database
DATABASE_URL=sqlite:///./data/database.db

# YouTube API (Optional - for faster crawling)
YOUTUBE_API_KEY=your-youtube-api-key-here

# AI Summarization - Choose one:

# Option 1: OpenAI (if available in your region)
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4
USE_DEEPSEEK=False

# Option 2: DeepSeek (recommended for regions where OpenAI is blocked)
DEEPSEEK_API_KEY=your-deepseek-api-key-here
DEEPSEEK_MODEL=deepseek-chat
USE_DEEPSEEK=True

# Crawler Settings
MAX_VIDEOS_PER_CHANNEL=50
AUTO_SUMMARIZE=True
```

4. **Run the application**
```bash
python run.py
```

5. **Access the web interface**
- **Dashboard**: http://127.0.0.1:5000/dashboard
- **API Docs**: http://127.0.0.1:5000/docs

## 📖 Usage Guide

### Adding Channels

1. Navigate to the **Channels** page
2. Click **"Add Channel"**
3. Fill in the form:
   - **Reference ID**: Your unique identifier (e.g., `mkbhd`, `tech-channel-1`)
   - **Channel Name**: Display name (e.g., `MKBHD`)
   - **YouTube URL**: Any YouTube channel URL format
   - **Keywords**: Optional comma-separated keywords for filtering
4. Click **"Add Channel"**

### Starting a Crawl

1. Go to the **Dashboard**
2. Click **"Start New Crawl"**
3. Select channels to crawl
4. Add filter keywords (optional)
5. Click **"Start Crawl"**
6. Monitor real-time progress

### Viewing Videos

1. Navigate to the **Videos** page
2. Use search and filters to find videos
3. Click on a video to view details
4. Generate AI summaries on demand

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | FastAPI |
| **Database** | SQLite + SQLAlchemy ORM |
| **YouTube Data** | yt-dlp + YouTube Data API v3 |
| **Transcription** | youtube-transcript-api |
| **AI Summarization** | OpenAI GPT-4 / DeepSeek |
| **Task Scheduling** | APScheduler |
| **Real-time Updates** | WebSocket |
| **Frontend** | HTML/CSS/JavaScript + Bootstrap 5 |

## 🔑 API Keys Setup

### YouTube API Key (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable YouTube Data API v3
4. Create credentials (API Key)
5. Add to `.env` file

### DeepSeek API Key (Recommended)

1. Visit [DeepSeek Platform](https://platform.deepseek.com/)
2. Sign up for an account
3. Generate an API key
4. Add to `.env` file with `USE_DEEPSEEK=True`

### OpenAI API Key (Alternative)

1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Sign up and add payment method
3. Generate an API key
4. Add to `.env` file with `USE_DEEPSEEK=False`

## 📊 API Documentation

Access the interactive API documentation at:
- **Swagger UI**: http://127.0.0.1:5000/docs
- **ReDoc**: http://127.0.0.1:5000/redoc

### Key Endpoints

- `GET /api/channels/` - List all channels (includes `category_id` and `category`; filter with `?category_id=`)
- `POST /api/channels/` - Add new channel
- `GET /api/categories/` - List categories with `channel_count`
- `GET /api/categories/{id}/channels` - Channels in a category (`id` is the numeric id or the slug)
- `GET /api/videos/` - List videos with filters
- `POST /api/sessions/start` - Start crawl session
- `POST /api/videos/{id}/summarize` - Generate video summary

## Channel categories

Categories live in the `categories` table (`slug`, `name_zh`, `name_en`, `sort_order`). Each channel stores `category_id`. The slug values (`hk-news`, `tech`, `other`, …) come from `data/channel_catalog_seed.json`.

On startup the app upserts those categories and assigns channels that are already in the database. It does not insert new channels and it does not delete channels or videos.

To run the same backfill yourself, including inside Docker against the SQLite file:

```bash
python scripts/seed_channel_categories.py
docker compose exec youtube-crawler python scripts/seed_channel_categories.py
```

The script is safe to re-run. Existing channels are matched to catalog search names by YouTube channel id, channel URL, or a clear name alias (MKBHD / Marques Brownlee, HOY / 有線新聞, memehongkong / 謎米香港, SCMP, 明報, RTHK, TVB News, and the other groups in `app/services/channel_catalog.py`). A match only sets the category. BBC News and BBC News 中文 stay separate.

Catalog rows are inserted only when the seed file already has a verified `youtube_channel_id` (`resolved_by` of `youtube_data_api`, `yt-dlp`, or `manual`). Lookups keep a channel when the title clearly matches (including any HK / 香港 token), it has at least 1,000 subscribers, and a short name is echoed by the handle or description. To look ids up and then import the ones that pass:

```bash
python scripts/seed_channel_categories.py --resolve
```

`--dry-run` prints the report and rolls the database back. Newly imported channels are `crawl_enabled=false` unless you pass `--enable-crawl`. Channels that were already stored keep their `crawl_enabled` flag.

## 📁 Project Structure

```
youtube-crawler/
├── app/
│   ├── main.py                    # FastAPI application entry
│   ├── config.py                  # Configuration management
│   ├── database.py                # Database connection
│   ├── models/                    # SQLAlchemy models
│   │   ├── channel.py             # Channel model
│   │   ├── video.py               # Video model
│   │   └── crawl_session.py       # Crawl session model
│   ├── schemas/                   # Pydantic schemas
│   │   ├── channel.py             # Channel schemas
│   │   ├── video.py               # Video schemas
│   │   └── session.py             # Session schemas
│   ├── api/                       # API routes
│   │   ├── channels.py            # Channel endpoints
│   │   ├── videos.py              # Video endpoints
│   │   ├── sessions.py            # Session endpoints
│   │   ├── dashboard.py           # Dashboard endpoints
│   │   └── websocket.py           # WebSocket endpoints
│   ├── services/                  # Business logic
│   │   ├── youtube_service.py     # YouTube data fetching
│   │   ├── crawler_service.py     # Video crawling logic
│   │   ├── transcript_service.py  # Transcript extraction
│   │   ├── summarizer_service.py  # AI summarization
│   │   └── filter_service.py      # Keyword filtering
│   ├── tasks/                     # Background tasks
│   │   └── scheduler.py           # APScheduler tasks
│   └── templates/                 # HTML templates
│       ├── base.html              # Base template
│       ├── dashboard.html         # Dashboard page
│       ├── channels.html          # Channels page
│       ├── videos.html            # Videos page
│       └── sessions.html          # Sessions page
├── static/                        # Frontend assets
│   ├── css/
│   │   └── style.css              # Custom styles
│   └── js/
│       ├── dashboard.js           # Dashboard logic
│       ├── channels.js            # Channels logic
│       ├── videos.js              # Videos logic
│       ├── sessions.js            # Sessions logic
│       └── websocket.js           # WebSocket client
├── data/                          # Data directory
│   ├── database.db                # SQLite database (auto-created)
│   └── logs/                      # Application logs
├── .env                           # Environment variables
├── .gitignore                     # Git ignore rules
├── requirements.txt               # Python dependencies
├── run.py                         # Application runner
└── README.md                      # This file
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `APP_NAME` | Application name | YouTube Crawler | No |
| `DEBUG` | Debug mode | True | No |
| `DATABASE_URL` | Database connection string | sqlite:///./data/database.db | No |
| `YOUTUBE_API_KEY` | YouTube Data API key | None | No |
| `DEEPSEEK_API_KEY` | DeepSeek API key | None | Yes* |
| `OPENAI_API_KEY` | OpenAI API key | None | Yes* |
| `USE_DEEPSEEK` | Use DeepSeek instead of OpenAI | False | No |
| `MAX_VIDEOS_PER_CHANNEL` | Max videos to crawl per channel | 50 | No |
| `AUTO_SUMMARIZE` | Auto-generate summaries | True | No |
| `ENABLE_SCHEDULER` | Enable scheduled crawls | True | No |

*At least one AI API key is required for summarization features

## 🐛 Troubleshooting

### Server won't start
- Check if port 5000 is already in use
- Verify Python version is 3.8+
- Ensure all dependencies are installed

### Can't add channels
- Verify the YouTube URL format is correct
- Check internet connection
- Review server logs for errors

### Summarization not working
- Verify API key is correct in `.env`
- Check if `USE_DEEPSEEK` is set correctly
- Ensure you have API credits/quota remaining
- For OpenAI region blocks, switch to DeepSeek

### Crawling fails
- Check YouTube API quota (if using API key)
- Verify channel URLs are accessible
- Check internet connection
- Review crawler logs in `data/logs/`

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube data extraction
- [OpenAI](https://openai.com/) - AI summarization
- [DeepSeek](https://www.deepseek.com/) - Alternative AI provider
- [Bootstrap](https://getbootstrap.com/) - UI framework

## 📧 Support

For issues and questions:
- Open an issue on [GitHub](https://github.com/kenkenlee/youtube-crawler/issues)
- Check existing documentation
- Review troubleshooting section

## 🗺️ Roadmap

- [ ] Video download functionality
- [ ] Multi-language support
- [ ] Advanced analytics
- [ ] Email notifications
- [ ] Docker support
- [ ] Cloud deployment guides
- [ ] Mobile-responsive improvements
- [ ] Batch operations

---

**Made with ❤️ by the YouTube Crawler Team**
