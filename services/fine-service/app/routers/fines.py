import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db, utcnow
from app.models import Fine, Payment
from app.utils.pagination import Page, PageParams, paginate
from app.schemas import AssessRequest, FineDetail, FineOut, FineSummary, ManualFine
from app.core.security import CurrentUser, ensure_owner_or_admin, get_current_user, require_admin, verify_internal_key

router = APIRouter(prefix="/fines", tags=["fines"])

FINE_PER_DAY = float(os.environ.get("FINE_PER_DAY", "0.50"))
MAX_FINE = float(os.environ.get("MAX_FINE", "25.00"))


@router.post("/internal/assess", response_model=FineOut, include_in_schema=False)
def internal_assess(body: AssessRequest, _: None = Depends(verify_internal_key), db: Session = Depends(get_db)):
    """Called by the Borrowing service on a late return. Idempotent per loan."""
    existing = db.scalar(select(Fine).where(Fine.loan_id == body.loan_id))
    if existing:
        return existing
    amount = round(min(body.days_overdue * FINE_PER_DAY, MAX_FINE), 2)
    fine = Fine(user_id=body.user_id, loan_id=body.loan_id, amount=amount,
                reason=f"Late return: {body.days_overdue} day(s) overdue")
    db.add(fine)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.scalar(select(Fine).where(Fine.loan_id == body.loan_id))
    return fine


@router.get("/my", response_model=Page[FineOut])
def my_fines(status: str | None = Query(None, pattern="^(UNPAID|PAID)$"), params: PageParams = Depends(),
             current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """The logged-in user's fines."""
    stmt = select(Fine).where(Fine.user_id == current.id).order_by(Fine.id.desc())
    if status:
        stmt = stmt.where(Fine.status == status)
    return paginate(db, stmt, params)


@router.get("/my/summary", response_model=FineSummary)
def my_summary(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Totals of what the logged-in user owes / has paid."""
    rows = dict(db.execute(select(Fine.status, func.coalesce(func.sum(Fine.amount), 0.0))
                           .where(Fine.user_id == current.id).group_by(Fine.status)).all())
    unpaid_count = db.scalar(select(func.count()).select_from(Fine)
                             .where(Fine.user_id == current.id, Fine.status == "UNPAID")) or 0
    return FineSummary(unpaid_count=unpaid_count, unpaid_total=round(rows.get("UNPAID", 0.0), 2),
                       paid_total=round(rows.get("PAID", 0.0), 2))


@router.get("", response_model=Page[FineOut])
def list_fines(status: str | None = Query(None, pattern="^(UNPAID|PAID)$"), user_id: int | None = None,
               params: PageParams = Depends(), _=Depends(require_admin), db: Session = Depends(get_db)):
    """ADMIN only: every fine."""
    stmt = select(Fine).order_by(Fine.id.desc())
    if status:
        stmt = stmt.where(Fine.status == status)
    if user_id:
        stmt = stmt.where(Fine.user_id == user_id)
    return paginate(db, stmt, params)


@router.post("", response_model=FineOut, status_code=201)
def create_fine(body: ManualFine, _=Depends(require_admin), db: Session = Depends(get_db)):
    """ADMIN only: add a manual fine (e.g. damaged or lost book)."""
    fine = Fine(**body.model_dump())
    db.add(fine)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A fine already exists for that loan.") from None
    return fine


@router.get("/{fine_id}", response_model=FineDetail)
def get_fine(fine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """One fine with its payment receipts (owner or ADMIN)."""
    fine = db.get(Fine, fine_id)
    if not fine:
        raise HTTPException(404, "Fine not found.")
    ensure_owner_or_admin(current, fine.user_id)
    return fine


@router.post("/{fine_id}/pay", response_model=FineDetail)
def pay_fine(fine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Pay a fine (the owner or an ADMIN at the desk). Creates a payment receipt."""
    fine = db.get(Fine, fine_id)
    if not fine:
        raise HTTPException(404, "Fine not found.")
    ensure_owner_or_admin(current, fine.user_id)
    if fine.status == "PAID":
        raise HTTPException(409, "This fine is already paid.")
    now = utcnow()
    fine.status = "PAID"
    fine.paid_at = now
    fine.payments.append(Payment(amount=fine.amount, paid_by=current.id, paid_at=now))
    db.commit()
    return fine


@router.delete("/{fine_id}", status_code=204)
def waive_fine(fine_id: int, _=Depends(require_admin), db: Session = Depends(get_db)):
    """ADMIN only: waive (delete) a fine that has not been paid."""
    fine = db.get(Fine, fine_id)
    if not fine:
        raise HTTPException(404, "Fine not found.")
    if fine.status == "PAID":
        raise HTTPException(409, "A paid fine cannot be deleted.")
    db.delete(fine)
    db.commit()
