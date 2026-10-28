from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Category(Base):
    """Editorial category for channels (slug matches the catalog id)."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    name_zh = Column(String(200), nullable=False)
    name_en = Column(String(200), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    channels = relationship("Channel", back_populates="category")

    def __repr__(self):
        return f"<Category(slug='{self.slug}', zh='{self.name_zh}')>"
