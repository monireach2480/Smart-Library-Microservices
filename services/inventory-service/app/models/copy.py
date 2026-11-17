from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utcnow


class BookCopy(Base):
    """One physical copy of a catalogue book."""
    __tablename__ = "book_copies"
    __table_args__ = (CheckConstraint("status IN ('AVAILABLE','BORROWED','LOST','MAINTENANCE')",
                                      name="ck_copies_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(Integer, index=True)            # id in the Catalog service
    barcode: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    shelf_location: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="AVAILABLE", index=True)  # AVAILABLE|BORROWED|LOST|MAINTENANCE
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
