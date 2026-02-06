import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Create a test client with database override"""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_channel_data():
    """Sample channel data for testing"""
    return {
        "channel_id": "test-channel",
        "channel_name": "Test Channel",
        "channel_url": "https://www.youtube.com/@test",
        "description": "Test channel description",
        "keywords": ["test", "sample"],
        "crawl_enabled": True,
        "crawl_frequency": "manual"
    }


@pytest.fixture
def sample_video_data():
    """Sample video data for testing"""
    return {
        "video_id": "test-video-123",
        "title": "Test Video",
        "description": "Test video description",
        "duration": 300,
        "view_count": 1000,
        "like_count": 50,
        "comment_count": 10,
        "video_url": "https://www.youtube.com/watch?v=test-video-123"
    }
