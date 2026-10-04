import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.passwords import hash_password
from app.schemas import EmailCheck, RegisterRequest, UserOut

router = APIRouter(tags=["registration"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
):
    """Public sign-up. New accounts are MEMBERs. An ADMIN account can only be created by sending the
    secret `X-Admin-Key` header (value = ADMIN_REGISTRATION_KEY on the server)."""
    if body.role == "ADMIN":
        expected = os.environ.get("ADMIN_REGISTRATION_KEY", "")
        if not expected or not x_admin_key or not hmac.compare_digest(x_admin_key, expected):
            raise HTTPException(403, "Creating an ADMIN requires a valid X-Admin-Key header.")

    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")

    user = User(name=body.name, email=email, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists.") from None
    return user


@router.get("/check-email", response_model=EmailCheck)
def check_email(email: str = Query(min_length=3, max_length=255), db: Session = Depends(get_db)):
    """Is this email still free to register?"""
    taken = db.scalar(select(User.id).where(User.email == email.strip().lower())) is not None
    return EmailCheck(email=email, available=not taken)
