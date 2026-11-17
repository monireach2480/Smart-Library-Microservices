import math
import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients import call_service
from app.core.database import as_utc, get_db, utcnow
from app.models import Loan
from app.utils.pagination import Page, PageParams, paginate
from app.schemas import BorrowRequest, LoanOut
from app.core.security import CurrentUser, ensure_owner_or_admin, get_current_user, require_admin, require_member

router = APIRouter(prefix="/loans", tags=["loans"])

INVENTORY_URL = os.environ.get("INVENTORY_URL", "http://inventory-service:8005")
MEMBER_URL = os.environ.get("MEMBER_URL", "http://member-service:8004")
FINE_URL = os.environ.get("FINE_URL", "http://fine-service:8007")
LOAN_DAYS = int(os.environ.get("LOAN_DAYS", "14"))
MAX_ACTIVE_LOANS = int(os.environ.get("MAX_ACTIVE_LOANS", "5"))


@router.post("", response_model=LoanOut, status_code=201)
def borrow_book(body: BorrowRequest, current: CurrentUser = Depends(require_member),
                db: Session = Depends(get_db)):
    """MEMBER only: borrow a book. Checks the account is ACTIVE, the loan limit, then reserves a copy."""
    r = call_service("GET", MEMBER_URL, f"/members/internal/{current.id}/status", internal=True)
    if r.status_code != 200 or r.json().get("status") != "ACTIVE":
        raise HTTPException(403, "Your account is not active.")

    active = db.scalar(select(func.count()).select_from(Loan)
                       .where(Loan.user_id == current.id, Loan.status == "ACTIVE")) or 0
    if active >= MAX_ACTIVE_LOANS:
        raise HTTPException(409, f"Loan limit reached ({MAX_ACTIVE_LOANS} active loans).")

    dup = db.scalar(select(Loan.id).where(Loan.user_id == current.id, Loan.book_id == body.book_id,
                                          Loan.status == "ACTIVE"))
    if dup:
        raise HTTPException(409, "You already have this book on loan.")

    r = call_service("POST", INVENTORY_URL, "/inventory/internal/checkout",
                     json={"book_id": body.book_id}, internal=True)
    if r.status_code == 409:
        raise HTTPException(409, "No copy of this book is available right now.")
    if r.status_code != 200:
        raise HTTPException(502, "Inventory service returned an unexpected response.")
    copy_id = r.json()["id"]

    now = utcnow()
    loan = Loan(user_id=current.id, book_id=body.book_id, copy_id=copy_id, borrowed_at=now,
                due_at=now + timedelta(days=LOAN_DAYS))
    db.add(loan)
    try:
        db.commit()
    except Exception:
        db.rollback()
        call_service("POST", INVENTORY_URL, "/inventory/internal/return", json={"copy_id": copy_id}, internal=True)
        raise
    return loan


@router.get("/my", response_model=Page[LoanOut])
def my_loans(status: str | None = Query(None, pattern="^(ACTIVE|RETURNED)$"), params: PageParams = Depends(),
             current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """The logged-in user's loans."""
    stmt = select(Loan).where(Loan.user_id == current.id).order_by(Loan.id.desc())
    if status:
        stmt = stmt.where(Loan.status == status)
    return paginate(db, stmt, params)


@router.get("", response_model=Page[LoanOut])
def list_loans(
    status: str | None = Query(None, pattern="^(ACTIVE|RETURNED)$"),
    user_id: int | None = None,
    overdue: bool | None = Query(None, description="true = active loans past their due date"),
    params: PageParams = Depends(),
    _=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """ADMIN only: all loans, with filters."""
    stmt = select(Loan).order_by(Loan.id.desc())
    if status:
        stmt = stmt.where(Loan.status == status)
    if user_id:
        stmt = stmt.where(Loan.user_id == user_id)
    if overdue:
        stmt = stmt.where(Loan.status == "ACTIVE", Loan.due_at < utcnow())
    return paginate(db, stmt, params)


@router.get("/{loan_id}", response_model=LoanOut)
def get_loan(loan_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    loan = db.get(Loan, loan_id)
    if not loan:
        raise HTTPException(404, "Loan not found.")
    ensure_owner_or_admin(current, loan.user_id)
    return loan


@router.post("/{loan_id}/return", response_model=LoanOut)
def return_book(loan_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return a book (the borrower or an ADMIN). Late returns automatically create a fine in the Fine service."""
    loan = db.get(Loan, loan_id)
    if not loan:
        raise HTTPException(404, "Loan not found.")
    ensure_owner_or_admin(current, loan.user_id)
    if loan.status != "ACTIVE":
        raise HTTPException(409, "This loan has already been returned.")

    now = utcnow()
    fine_amount = 0.0
    if now > as_utc(loan.due_at):
        days_overdue = math.ceil((now - as_utc(loan.due_at)).total_seconds() / 86400)
        r = call_service("POST", FINE_URL, "/fines/internal/assess", internal=True,
                         json={"loan_id": loan.id, "user_id": loan.user_id, "days_overdue": days_overdue})
        if r.status_code != 200:
            raise HTTPException(502, "Fine service could not assess the late fee; please retry.")
        fine_amount = float(r.json()["amount"])

    r = call_service("POST", INVENTORY_URL, "/inventory/internal/return",
                     json={"copy_id": loan.copy_id}, internal=True)
    if r.status_code != 200:
        raise HTTPException(502, "Inventory service could not accept the return; please retry.")

    loan.status = "RETURNED"
    loan.returned_at = now
    loan.fine_amount = fine_amount
    db.commit()
    return loan
