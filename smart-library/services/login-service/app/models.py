# AUTO-COPIED from services/_common/users_model.py - edit it there and run scripts/sync_common.py
"""The `users` table. Registration, Login and Member services share the same auth database."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('ADMIN','MEMBER')", name="ck_users_role"),
        CheckConstraint("status IN ('ACTIVE','SUSPENDED')", name="ck_users_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="MEMBER")      # ADMIN | MEMBER
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")    # ACTIVE | SUSPENDED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
