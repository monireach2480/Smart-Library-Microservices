from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow


class Fine(Base):
    __tablename__ = "fines"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_fines_amount"),
        CheckConstraint("status IN ('UNPAID','PAID')", name="ck_fines_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    loan_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)  # one automatic fine per loan
    amount: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="UNPAID", index=True)     # UNPAID | PAID
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    payments: Mapped[list["Payment"]] = relationship(back_populates="fine", cascade="all, delete-orphan",
                                                     order_by="Payment.id")


class Payment(Base):
    """Receipt created when a fine is paid."""
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    fine_id: Mapped[int] = mapped_column(ForeignKey("fines.id", ondelete="CASCADE"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    paid_by: Mapped[int] = mapped_column(Integer)          # user id of whoever paid (owner or an ADMIN at the desk)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    fine: Mapped[Fine] = relationship(back_populates="payments")
