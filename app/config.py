from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "YouTube Crawler"
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-this"

    # Database
    DATABASE_URL: str = "sqlite:///./data/database.db"

    # YouTube API
    YOUTUBE_API_KEY: Optional[str] = None

    # OpenAI API
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4"
    OPENAI_MAX_TOKENS: int = 1000

    # DeepSeek API (alternative to OpenAI)
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    USE_DEEPSEEK: bool = False

    # Crawler Settings
    MAX_CONCURRENT_CRAWLS: int = 3
    MAX_VIDEOS_PER_CHANNEL: int = 50
    CRAWL_DELAY_SECONDS: int = 1

    # Summarization
    AUTO_SUMMARIZE: bool = True
    SUMMARY_STYLE: str = "concise"

    # Scheduler
    ENABLE_SCHEDULER: bool = True
    DAILY_CRAWL_TIME: str = "02:00"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
