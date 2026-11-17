from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    books: Mapped[list["Book"]] = relationship(back_populates="category_ref")


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (CheckConstraint("published_year IS NULL OR published_year BETWEEN 1000 AND 2100",
                                      name="ck_books_year"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    author: Mapped[str] = mapped_column(String(200), index=True)
    isbn: Mapped[str] = mapped_column(String(13), unique=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)   # N books : 1 category
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    language: Mapped[str] = mapped_column(String(50), default="English")
    published_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    category_ref: Mapped[Category] = relationship(back_populates="books", lazy="joined")

    @property
    def category(self) -> str:          # the API keeps exposing the category as a plain name
        return self.category_ref.name
