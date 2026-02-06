# YouTube Channel Crawler Tests

This directory contains tests for the YouTube Channel Crawler application.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest configuration and fixtures
├── test_api/                # API endpoint tests
│   ├── test_channels.py
│   ├── test_videos.py
│   ├── test_sessions.py
│   └── test_dashboard.py
├── test_services/           # Service layer tests
│   ├── test_youtube_service.py
│   ├── test_crawler_service.py
│   ├── test_summarizer_service.py
│   └── test_export_service.py
└── test_models/             # Database model tests
    ├── test_channel.py
    ├── test_video.py
    └── test_session.py
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=app --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_api/test_channels.py
```

### Run specific test
```bash
pytest tests/test_api/test_channels.py::test_create_channel
```

### Run with verbose output
```bash
pytest -v
```

## Writing Tests

### Example Test

```python
import pytest
from fastapi.testclient import TestClient

def test_list_channels(client):
    """Test listing channels"""
    response = client.get("/api/channels/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_channel(client):
    """Test creating a channel"""
    channel_data = {
        "channel_id": "test-channel",
        "channel_name": "Test Channel",
        "channel_url": "https://www.youtube.com/@test"
    }
    response = client.post("/api/channels/", json=channel_data)
    assert response.status_code == 201
    assert response.json()["channel_id"] == "test-channel"
```

## Test Coverage

Current coverage: TBD

Target coverage: 80%+

## CI/CD Integration

Tests are automatically run on:
- Every push to main/develop branches
- Every pull request
- Multiple Python versions (3.8, 3.9, 3.10, 3.11)
