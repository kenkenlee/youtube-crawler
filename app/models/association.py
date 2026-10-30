from sqlalchemy import Table, Column, Integer, ForeignKey
from app.database import Base

# Many-to-many: a channel may belong to one or more categories.
channel_categories = Table(
    "channel_categories",
    Base.metadata,
    Column("channel_id", Integer, ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)
