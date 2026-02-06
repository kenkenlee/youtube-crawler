# API Documentation

## Overview

The YouTube Channel Crawler provides a RESTful API built with FastAPI. All endpoints return JSON responses and follow standard HTTP status codes.

**Base URL**: `http://127.0.0.1:5000`

**Interactive Documentation**:
- Swagger UI: http://127.0.0.1:5000/docs
- ReDoc: http://127.0.0.1:5000/redoc

## Authentication

Currently, the API does not require authentication. This may be added in future versions.

## Response Format

### Success Response
```json
{
  "data": {...},
  "message": "Success"
}
```

### Error Response
```json
{
  "detail": "Error message"
}
```

## Endpoints

### Channels

#### List All Channels
```http
GET /api/channels/
```

**Query Parameters**:
- `skip` (integer, optional): Number of records to skip (default: 0)
- `limit` (integer, optional): Maximum records to return (default: 100)

**Response**:
```json
[
  {
    "id": 1,
    "channel_id": "mkbhd",
    "youtube_channel_id": "UCBJycsmduvYEL83R_U4JriQ",
    "channel_name": "MKBHD",
    "channel_url": "https://www.youtube.com/@mkbhd",
    "description": "Tech reviews and more",
    "keywords": ["tech", "review", "smartphone"],
    "crawl_enabled": true,
    "crawl_frequency": "manual",
    "last_crawled_at": "2024-02-06T10:30:00",
    "created_at": "2024-02-01T08:00:00",
    "updated_at": "2024-02-06T10:30:00"
  }
]
```

#### Get Channel by ID
```http
GET /api/channels/{channel_id}
```

**Path Parameters**:
- `channel_id` (integer, required): Channel database ID

**Response**: Single channel object (same format as above)

#### Create Channel
```http
POST /api/channels/
```

**Request Body**:
```json
{
  "channel_id": "mkbhd",
  "channel_name": "MKBHD",
  "channel_url": "https://www.youtube.com/@mkbhd",
  "description": "Tech reviews and more",
  "keywords": ["tech", "review", "smartphone"],
  "crawl_enabled": true,
  "crawl_frequency": "manual"
}
```

**Response**: Created channel object with status 201

#### Update Channel
```http
PUT /api/channels/{channel_id}
```

**Path Parameters**:
- `channel_id` (integer, required): Channel database ID

**Request Body**: Same as create (all fields optional)

**Response**: Updated channel object

#### Delete Channel
```http
DELETE /api/channels/{channel_id}
```

**Path Parameters**:
- `channel_id` (integer, required): Channel database ID

**Response**: 204 No Content

---

### Videos

#### List Videos
```http
GET /api/videos/
```

**Query Parameters**:
- `skip` (integer, optional): Number of records to skip (default: 0)
- `limit` (integer, optional): Maximum records to return (default: 20)
- `channel_id` (integer, optional): Filter by channel ID
- `search` (string, optional): Search in title and description
- `has_summary` (boolean, optional): Filter by summary availability

**Response**:
```json
{
  "items": [
    {
      "id": 1,
      "video_id": "dQw4w9WgXcQ",
      "channel_id": 1,
      "title": "Amazing Tech Review",
      "description": "Full review of the latest gadget",
      "published_at": "2024-02-05T12:00:00",
      "duration": 600,
      "view_count": 1000000,
      "like_count": 50000,
      "comment_count": 2000,
      "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
      "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "summary": "This video reviews...",
      "has_transcript": true,
      "created_at": "2024-02-06T10:30:00"
    }
  ],
  "total": 100,
  "page": 1,
  "pages": 5
}
```

#### Get Video by ID
```http
GET /api/videos/{video_id}
```

**Path Parameters**:
- `video_id` (integer, required): Video database ID

**Response**: Single video object

#### Get Video Transcript
```http
GET /api/videos/{video_id}/transcript
```

**Path Parameters**:
- `video_id` (integer, required): Video database ID

**Response**:
```json
{
  "video_id": 1,
  "transcript": "Full transcript text...",
  "language": "en"
}
```

#### Generate Video Summary
```http
POST /api/videos/{video_id}/summarize
```

**Path Parameters**:
- `video_id` (integer, required): Video database ID

**Query Parameters**:
- `style` (string, optional): Summary style - `concise`, `detailed`, or `bullet_points` (default: concise)

**Response**:
```json
{
  "video_id": 1,
  "summary": "Generated summary text...",
  "style": "concise"
}
```

---

### Crawl Sessions

#### List Sessions
```http
GET /api/sessions/
```

**Query Parameters**:
- `skip` (integer, optional): Number of records to skip (default: 0)
- `limit` (integer, optional): Maximum records to return (default: 20)
- `status` (string, optional): Filter by status - `pending`, `running`, `completed`, `failed`

**Response**:
```json
[
  {
    "id": 1,
    "session_name": "Manual Crawl - 2024-02-06",
    "status": "completed",
    "channels_count": 3,
    "videos_found": 150,
    "videos_processed": 150,
    "filter_keywords": ["tech", "review"],
    "started_at": "2024-02-06T10:00:00",
    "completed_at": "2024-02-06T10:45:00",
    "error_message": null,
    "created_at": "2024-02-06T10:00:00"
  }
]
```

#### Get Session by ID
```http
GET /api/sessions/{session_id}
```

**Path Parameters**:
- `session_id` (integer, required): Session database ID

**Response**: Single session object with detailed progress

#### Start Crawl Session
```http
POST /api/sessions/start
```

**Request Body**:
```json
{
  "channel_ids": [1, 2, 3],
  "filter_keywords": ["tech", "review"],
  "max_videos_per_channel": 50,
  "auto_summarize": true
}
```

**Response**:
```json
{
  "session_id": 1,
  "status": "running",
  "message": "Crawl session started"
}
```

#### Stop Crawl Session
```http
POST /api/sessions/{session_id}/stop
```

**Path Parameters**:
- `session_id` (integer, required): Session database ID

**Response**:
```json
{
  "session_id": 1,
  "status": "stopped",
  "message": "Crawl session stopped"
}
```

---

### Dashboard

#### Get Dashboard Statistics
```http
GET /api/dashboard/stats
```

**Response**:
```json
{
  "total_channels": 10,
  "total_videos": 500,
  "total_sessions": 25,
  "active_sessions": 1,
  "videos_with_summaries": 450,
  "last_crawl": "2024-02-06T10:45:00"
}
```

#### Get Recent Activity
```http
GET /api/dashboard/recent-activity
```

**Query Parameters**:
- `limit` (integer, optional): Maximum records to return (default: 10)

**Response**:
```json
[
  {
    "type": "crawl_completed",
    "message": "Crawl session completed: 50 videos processed",
    "timestamp": "2024-02-06T10:45:00"
  },
  {
    "type": "channel_added",
    "message": "New channel added: MKBHD",
    "timestamp": "2024-02-06T09:30:00"
  }
]
```

#### Get Channels Summary
```http
GET /api/dashboard/channels-summary
```

**Query Parameters**:
- `limit` (integer, optional): Maximum records to return (default: 10)

**Response**:
```json
[
  {
    "channel_id": 1,
    "channel_name": "MKBHD",
    "video_count": 50,
    "last_crawled": "2024-02-06T10:30:00",
    "avg_views": 1000000
  }
]
```

#### Get Daily Summary
```http
GET /api/dashboard/daily-summary
```

**Query Parameters**:
- `days` (integer, optional): Number of days to include (default: 7)

**Response**:
```json
[
  {
    "date": "2024-02-06",
    "videos_added": 50,
    "summaries_generated": 45,
    "crawl_sessions": 2
  }
]
```

---

### WebSocket

#### Real-time Crawl Updates
```
WS /ws/crawl/{session_id}
```

**Path Parameters**:
- `session_id` (integer, required): Session database ID

**Message Format**:
```json
{
  "type": "progress",
  "session_id": 1,
  "channel": "MKBHD",
  "videos_processed": 25,
  "total_videos": 50,
  "current_video": "Amazing Tech Review",
  "status": "processing"
}
```

**Message Types**:
- `progress`: Crawl progress update
- `completed`: Crawl completed
- `error`: Error occurred
- `video_added`: New video added
- `summary_generated`: Summary generated

---

## Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |

## Rate Limiting

Currently, there are no rate limits. This may be added in future versions.

## Error Handling

All errors return a JSON response with a `detail` field:

```json
{
  "detail": "Channel not found"
}
```

Validation errors return additional information:

```json
{
  "detail": [
    {
      "loc": ["body", "channel_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Examples

### Python Example

```python
import requests

# List channels
response = requests.get('http://127.0.0.1:5000/api/channels/')
channels = response.json()

# Add channel
new_channel = {
    "channel_id": "mkbhd",
    "channel_name": "MKBHD",
    "channel_url": "https://www.youtube.com/@mkbhd",
    "keywords": ["tech", "review"]
}
response = requests.post('http://127.0.0.1:5000/api/channels/', json=new_channel)
channel = response.json()

# Start crawl
crawl_config = {
    "channel_ids": [1, 2],
    "filter_keywords": ["tech"],
    "max_videos_per_channel": 50
}
response = requests.post('http://127.0.0.1:5000/api/sessions/start', json=crawl_config)
session = response.json()
```

### JavaScript Example

```javascript
// List videos
const response = await fetch('http://127.0.0.1:5000/api/videos/?limit=10');
const data = await response.json();
const videos = data.items;

// Generate summary
const videoId = 1;
const response = await fetch(
    `http://127.0.0.1:5000/api/videos/${videoId}/summarize?style=detailed`,
    { method: 'POST' }
);
const summary = await response.json();

// WebSocket connection
const ws = new WebSocket('ws://127.0.0.1:5000/ws/crawl/1');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Progress:', data);
};
```

### cURL Examples

```bash
# List channels
curl http://127.0.0.1:5000/api/channels/

# Add channel
curl -X POST http://127.0.0.1:5000/api/channels/ \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "mkbhd",
    "channel_name": "MKBHD",
    "channel_url": "https://www.youtube.com/@mkbhd"
  }'

# Start crawl
curl -X POST http://127.0.0.1:5000/api/sessions/start \
  -H "Content-Type: application/json" \
  -d '{
    "channel_ids": [1, 2],
    "filter_keywords": ["tech"]
  }'

# Get video summary
curl -X POST "http://127.0.0.1:5000/api/videos/1/summarize?style=concise"
```

---

## Changelog

### Version 1.0.0 (2024-02-06)
- Initial API release
- Channel management endpoints
- Video listing and search
- Crawl session management
- Real-time WebSocket updates
- AI summarization with DeepSeek/OpenAI support
