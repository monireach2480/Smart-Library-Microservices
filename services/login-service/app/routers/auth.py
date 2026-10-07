import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.core.passwords import DUMMY_HASH, hash_password, verify_password
from app.schemas import ChangePasswordRequest, LoginRequest, TokenResponse, UserOut, VerifyOut
from app.core.security import CurrentUser, get_current_user
from app.core.tokens import create_access_token

router = APIRouter(tags=["login"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Exchange email + password for a JWT (contains user id and role)."""
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # Always run one hash verification so timing does not reveal whether the email exists.
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok:
        raise HTTPException(401, "Invalid email or password.")
    if user.status != "ACTIVE":
        raise HTTPException(403, "This account is suspended. Please contact a librarian.")
    token, expires_in = create_access_token(user)
    return TokenResponse(access_token=token, expires_in=expires_in, user=user)


@router.get("/me", response_model=UserOut)
def me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Profile of the logged-in user (read from the database)."""
    user = db.get(User, current.id)
    if not user:
        raise HTTPException(404, "User no longer exists.")
    return user


@router.get("/verify", response_model=VerifyOut)
def verify(current: CurrentUser = Depends(get_current_user)):
    """Check that a token is valid and see which user/role it carries."""
    return VerifyOut(user_id=current.id, role=current.role, email=current.email)


@router.post("/change-password", status_code=204)
def change_password(body: ChangePasswordRequest, current: CurrentUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    user = db.get(User, current.id)
    if not user or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect.")
    if not (re.search(r"[A-Za-z]", body.new_password) and re.search(r"\d", body.new_password)):
        raise HTTPException(422, "New password must contain at least one letter and one digit.")
    user.password_hash = hash_password(body.new_password)
    db.commit()
