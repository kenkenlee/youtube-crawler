# YouTube Channel Crawler

A comprehensive YouTube channel crawler with video summarization capabilities, web interface for management, and automated crawling sessions with progress monitoring.

## Features

- 📺 YouTube channel management and video crawling
- 🤖 AI-powered video summarization using OpenAI GPT-4
- 🔍 Keyword-based video filtering
- 📊 Real-time progress monitoring with WebSocket
- ⏰ Scheduled automated crawls
- 📈 Dashboard with statistics and analytics
- 📤 Export data to Excel/CSV
- 🌐 Web interface for easy management

## Technology Stack

- **Backend**: FastAPI
- **Database**: SQLite with SQLAlchemy ORM
- **YouTube Data**: yt-dlp + YouTube Data API v3
- **Transcription**: youtube-transcript-api
- **Summarization**: OpenAI API (GPT-4)
- **Task Scheduling**: APScheduler
- **Frontend**: HTML/CSS/JavaScript with Bootstrap 5

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables in `.env`:
```
YOUTUBE_API_KEY=your-youtube-api-key-here
OPENAI_API_KEY=your-openai-api-key-here
```

## Usage

Run the application:
```bash
python run.py
```

Access the application at: http://localhost:8000

API documentation available at: http://localhost:8000/docs

## Project Structure

```
youtube-crawler/
├── app/
│   ├── main.py                    # FastAPI application entry
│   ├── config.py                  # Configuration management
│   ├── database.py                # Database connection
│   ├── models/                    # SQLAlchemy models
│   ├── schemas/                   # Pydantic schemas
│   ├── api/                       # API routes
│   ├── services/                  # Business logic
│   ├── tasks/                     # Background tasks
│   └── templates/                 # HTML templates
├── static/                        # CSS and JavaScript
├── data/                          # Database and logs
├── .env                           # Environment variables
├── requirements.txt               # Dependencies
└── run.py                         # Application runner
```

## License

MIT
