from pydantic import BaseModel, Field


class CategorySummary(BaseModel):
    """Compact category payload embedded on channel responses."""

    id: int
    slug: str
    name_zh: str
    name_en: str

    class Config:
        from_attributes = True


class CategoryResponse(CategorySummary):
    sort_order: int


class CategoryWithCount(CategoryResponse):
    channel_count: int = Field(0, description="Channels currently assigned to this category")
