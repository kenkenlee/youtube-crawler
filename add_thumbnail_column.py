"""Add thumbnail_url column to channels table"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    # Add thumbnail_url column to channels table
    op.add_column('channels', sa.Column('thumbnail_url', sa.String(500), nullable=True))


def downgrade():
    # Remove thumbnail_url column
    op.drop_column('channels', 'thumbnail_url')
