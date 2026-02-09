# SQLite Database Manager

## Overview
The YouTube Crawler includes a web-based database management tool that allows you to view, query, and manage your database directly from your browser.

## How to Launch

### Option 1: Using the Python Script
```bash
python run_db_manager.py
```

### Option 2: Direct Command
```bash
python -m sqlite_web data/database.db --host 127.0.0.1 --port 8080
```

## Access
Once launched, open your browser and go to:
- **URL:** http://127.0.0.1:8080

## Features

### 1. View Tables
- Browse all database tables (channels, videos, crawl_sessions, etc.)
- View table schemas and indexes
- See row counts and table statistics

### 2. Query Data
- Run custom SQL queries
- Export query results to CSV
- View query execution plans

### 3. Browse Records
- Paginated table browsing
- Sort by any column
- Filter and search records

### 4. Edit Data (Use with Caution!)
- Update individual records
- Delete records
- Insert new records

### 5. Export Data
- Export entire tables to CSV
- Export query results
- Backup database

## Important Notes

⚠️ **Warning:** The database manager allows direct editing of your database. Use caution when:
- Deleting records
- Updating data
- Running DELETE or UPDATE queries

✅ **Best Practices:**
- Make backups before making changes
- Test queries on a copy first
- Use read-only queries when possible

## Common Queries

### View all channels with video counts
```sql
SELECT 
    c.channel_name,
    c.channel_url,
    COUNT(v.id) as video_count,
    c.last_crawled_at
FROM channels c
LEFT JOIN videos v ON c.id = v.channel_id
GROUP BY c.id
ORDER BY video_count DESC;
```

### Find videos without summaries
```sql
SELECT 
    v.title,
    c.channel_name,
    v.published_at
FROM videos v
JOIN channels c ON v.channel_id = c.id
WHERE v.summary_text IS NULL
ORDER BY v.published_at DESC
LIMIT 50;
```

### View crawl session statistics
```sql
SELECT 
    session_name,
    status,
    total_channels,
    videos_processed,
    videos_summarized,
    started_at,
    completed_at
FROM crawl_sessions
ORDER BY created_at DESC
LIMIT 20;
```

## Ports

- **Main Application:** http://127.0.0.1:5000
- **Database Manager:** http://127.0.0.1:8080

Both can run simultaneously!

## Stopping the Manager

Press `Ctrl+C` in the terminal where the database manager is running.
