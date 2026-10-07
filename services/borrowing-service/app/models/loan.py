from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utcnow


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (CheckConstraint("status IN ('ACTIVE','RETURNED')", name="ck_loans_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)     # id in the auth database
    book_id: Mapped[int] = mapped_column(Integer, index=True)     # id in the Catalog service
    copy_id: Mapped[int] = mapped_column(Integer)                 # id in the Inventory service
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)  # ACTIVE | RETURNED
    borrowed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fine_amount: Mapped[float] = mapped_column(Float, default=0.0)
