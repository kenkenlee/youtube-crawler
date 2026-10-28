from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class AppSetting(Base):
    """Key/value store for user-editable runtime settings.

    Settings edited from the Settings page are persisted here and take effect
    immediately (services read them on each instantiation), overriding the
    defaults loaded from .env / app.config.settings.
    """

    __tablename__ = "app_settings"

    key = Column(String(255), primary_key=True, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<AppSetting(key='{self.key}')>"
