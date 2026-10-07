from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    book_id: int = Field(gt=0)
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewUpdate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    book_id: int
    user_id: int
    user_name: str
    rating: int
    comment: str | None
    created_at: datetime
    updated_at: datetime


class RatingSummary(BaseModel):
    book_id: int
    review_count: int
    average_rating: float | None
    distribution: dict[int, int]
