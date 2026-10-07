from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("book_id", "user_id", name="uq_review_book_user"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    user_name: Mapped[str] = mapped_column(String(120))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
