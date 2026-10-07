from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.isbn import normalize_isbn


class BookBase(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    author: str = Field(min_length=1, max_length=200)
    isbn: str
    category: str = Field(min_length=1, max_length=100)
    publisher: str | None = Field(default=None, max_length=200)
    language: str = Field(default="English", max_length=50)
    published_year: int | None = Field(default=None, ge=1000, le=2100)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("isbn")
    @classmethod
    def valid_isbn(cls, v: str) -> str:
        return normalize_isbn(v)


class BookCreate(BookBase):
    pass


class BookUpdate(BookBase):
    pass


class BookOut(BookBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class CategoryOut(BaseModel):
    name: str
    book_count: int
