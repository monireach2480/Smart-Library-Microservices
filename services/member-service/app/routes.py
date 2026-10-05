from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.pagination import Page, PageParams, paginate
from app.schemas import MemberOut, MemberStatusOut, MemberUpdate, StatsOut, StatusUpdate
from app.security import (CurrentUser, ensure_owner_or_admin, get_current_user, require_admin,
                          verify_internal_key)

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=Page[MemberOut])
def list_members(
    q: str | None = Query(None, description="Search name or email"),
    role: str | None = Query(None, pattern="^(ADMIN|MEMBER)$"),
    status: str | None = Query(None, pattern="^(ACTIVE|SUSPENDED)$"),
    params: PageParams = Depends(),
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """ADMIN only: list / search all accounts."""
    stmt = select(User).order_by(User.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.name.ilike(like), User.email.ilike(like)))
    if role:
        stmt = stmt.where(User.role == role)
    if status:
        stmt = stmt.where(User.status == status)
    return paginate(db, stmt, params)


@router.get("/stats", response_model=StatsOut)
def stats(_: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    """ADMIN only: account counts by role and status."""
    by_role = dict(db.execute(select(User.role, func.count()).group_by(User.role)).all())
    by_status = dict(db.execute(select(User.status, func.count()).group_by(User.status)).all())
    return StatsOut(total=sum(by_role.values()), by_role=by_role, by_status=by_status)


@router.get("/internal/{member_id}/status", response_model=MemberStatusOut, include_in_schema=False)
def internal_status(member_id: int, _: None = Depends(verify_internal_key), db: Session = Depends(get_db)):
    """Used by the Borrowing service to check a member is ACTIVE. Not reachable through the gateway."""
    user = db.get(User, member_id)
    if not user:
        raise HTTPException(404, "Member not found.")
    return MemberStatusOut(id=user.id, status=user.status, role=user.role)


@router.get("/{member_id}", response_model=MemberOut)
def get_member(member_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """ADMIN can view anyone; a MEMBER can only view themself."""
    ensure_owner_or_admin(current, member_id)
    user = db.get(User, member_id)
    if not user:
        raise HTTPException(404, "Member not found.")
    return user


@router.put("/{member_id}", response_model=MemberOut)
def update_member(member_id: int, body: MemberUpdate, current: CurrentUser = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Update the display name (self or ADMIN)."""
    ensure_owner_or_admin(current, member_id)
    user = db.get(User, member_id)
    if not user:
        raise HTTPException(404, "Member not found.")
    user.name = body.name.strip()
    db.commit()
    return user


@router.patch("/{member_id}/status", response_model=MemberOut)
def set_status(member_id: int, body: StatusUpdate, current: CurrentUser = Depends(require_admin),
               db: Session = Depends(get_db)):
    """ADMIN only: suspend or re-activate an account (suspended users cannot log in)."""
    if member_id == current.id:
        raise HTTPException(400, "You cannot change your own status.")
    user = db.get(User, member_id)
    if not user:
        raise HTTPException(404, "Member not found.")
    user.status = body.status
    db.commit()
    return user
