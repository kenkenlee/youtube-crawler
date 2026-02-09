# YouTube Crawler - Deployment Guide

Complete guide for deploying the YouTube Crawler application with sample data.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Sample Data](#sample-data)
4. [Configuration](#configuration)
5. [Running the Application](#running-the-application)
6. [Docker Deployment](#docker-deployment)
7. [Production Deployment](#production-deployment)

---

## Quick Start

For a quick deployment with sample data:

```bash
# 1. Clone the repository
git clone https://github.com/kenkenlee/youtube-crawler.git
cd youtube-crawler

# 2. Install dependencies
pip install -r requirements.txt

# 3. Import sample data (optional)
python import_sample_data.py

# 4. Run the application
python run.py
```

Access the application at: http://127.0.0.1:5000

---

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git

### Step 1: Clone Repository

```bash
git clone https://github.com/kenkenlee/youtube-crawler.git
cd youtube-crawler
```

### Step 2: Create Virtual Environment (Recommended)

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and configure your settings (see [Configuration](#configuration) section).

---

## Sample Data

The repository includes sample data to help you get started quickly.

### Import Sample Data

```bash
python import_sample_data.py
```

This will import:
- 10 sample YouTube channels
- 50 sample videos with summaries
- 10 sample crawl sessions

### What You Get

After importing sample data, you can:
- Browse pre-populated channels
- View sample videos with AI-generated summaries
- See example crawl session history
- Test all features without waiting for crawls

### Export Your Own Sample Data

To create sample data from your database:

```bash
python export_sample_data.py
```

This exports:
- Up to 10 channels
- Up to 50 videos
- Up to 10 sessions

Files are saved to `sample_data/` directory.

---

## Configuration

### Environment Variables

Edit the `.env` file to configure the application:

#### Application Settings

```env
APP_NAME=YouTube Crawler
DEBUG=True
SECRET_KEY=your-secret-key-change-this-in-production
```

#### Database

```env
# SQLite (default - good for development)
DATABASE_URL=sqlite:///./data/database.db

# PostgreSQL (recommended for production)
# DATABASE_URL=postgresql://user:password@localhost/youtube_crawler
```

#### YouTube API (Optional)

```env
YOUTUBE_API_KEY=your-youtube-api-key-here
```

Get your API key from: https://console.cloud.google.com/

#### AI Summarization

**Option 1: OpenAI**
```env
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4
USE_DEEPSEEK=False
```

**Option 2: DeepSeek (Alternative)**
```env
DEEPSEEK_API_KEY=your-deepseek-api-key-here
DEEPSEEK_MODEL=deepseek-chat
USE_DEEPSEEK=True
```

#### Crawler Settings

```env
MAX_CONCURRENT_CRAWLS=3
MAX_VIDEOS_PER_CHANNEL=50
CRAWL_DELAY_SECONDS=1
AUTO_SUMMARIZE=True
```

#### Scheduler

```env
ENABLE_SCHEDULER=True
DAILY_CRAWL_TIME=02:00
```

---

## Running the Application

### Development Mode

```bash
python run.py
```

The server will start at: http://127.0.0.1:5000

Features:
- Auto-reload on code changes
- Debug mode enabled
- Detailed error messages

### Production Mode

For production, use a production ASGI server:

```bash
# Using Gunicorn with Uvicorn workers
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:5000

# Or using Uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 5000 --workers 4
```

---

## Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Build and start
docker-compose up -d

# Import sample data (optional)
docker-compose exec web python import_sample_data.py

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Using Dockerfile

```bash
# Build image
docker build -t youtube-crawler .

# Run container
docker run -d -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -e OPENAI_API_KEY=your-key \
  youtube-crawler

# Import sample data
docker exec -it <container-id> python import_sample_data.py
```

---

## Production Deployment

### Recommended Setup

1. **Web Server**: Nginx or Apache as reverse proxy
2. **ASGI Server**: Gunicorn with Uvicorn workers
3. **Database**: PostgreSQL
4. **Process Manager**: systemd or supervisor
5. **SSL**: Let's Encrypt certificates

### Example Nginx Configuration

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Systemd Service

Create `/etc/systemd/system/youtube-crawler.service`:

```ini
[Unit]
Description=YouTube Crawler
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/var/www/youtube-crawler
Environment="PATH=/var/www/youtube-crawler/venv/bin"
ExecStart=/var/www/youtube-crawler/venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:5000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable youtube-crawler
sudo systemctl start youtube-crawler
sudo systemctl status youtube-crawler
```

### Database Migration

For PostgreSQL:

```bash
# Create database
createdb youtube_crawler

# Update .env
DATABASE_URL=postgresql://user:password@localhost/youtube_crawler

# Initialize database (automatic on first run)
python run.py

# Import sample data
python import_sample_data.py
```

---

## Post-Deployment

### 1. Access the Application

Open your browser and navigate to:
- Development: http://127.0.0.1:5000
- Production: https://yourdomain.com

### 2. Add Your First Channel

1. Go to **Channels** page
2. Click **Add Channel**
3. Enter YouTube channel URL
4. Add keywords (optional)
5. Click **Add Channel**

### 3. Start Your First Crawl

1. Go to **Dashboard**
2. Click **New Crawl Session**
3. Select channels to crawl
4. Add filter keywords (optional)
5. Click **Start Crawl**

### 4. View Results

- **Videos**: Browse and search crawled videos
- **Dashboard**: View statistics and analytics
- **Sessions**: Monitor crawl progress and history

---

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 5000
lsof -i :5000  # Linux/Mac
netstat -ano | findstr :5000  # Windows

# Kill the process or use a different port
uvicorn app.main:app --port 8000
```

### Database Errors

```bash
# Reset database
rm data/database.db
python run.py  # Will recreate tables

# Re-import sample data
python import_sample_data.py
```

### Import Errors

```bash
# Check Python path
python -c "import sys; print(sys.path)"

# Ensure you're in the correct directory
cd youtube-crawler

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows
```

### API Key Issues

- Verify API keys are correct in `.env`
- Check API quotas and limits
- Ensure `.env` file is in the project root
- Restart the server after changing `.env`

---

## Maintenance

### Backup Database

```bash
# SQLite
cp data/database.db data/database.db.backup

# PostgreSQL
pg_dump youtube_crawler > backup.sql
```

### Update Application

```bash
git pull origin main
pip install -r requirements.txt --upgrade
python run.py
```

### Monitor Logs

```bash
# Development
# Logs appear in console

# Production (systemd)
sudo journalctl -u youtube-crawler -f

# Docker
docker-compose logs -f
```

---

## Support

For issues and questions:
- GitHub Issues: https://github.com/kenkenlee/youtube-crawler/issues
- Documentation: See README.md and other guides in the repository

---

## License

See LICENSE file in the repository.
