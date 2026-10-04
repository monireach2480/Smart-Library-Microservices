import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients import call_service
from app.database import get_db
from app.models import BookCopy
from app.pagination import Page, PageParams, paginate
from app.schemas import (AvailabilityOut, CheckoutRequest, CopyCreate, CopyOut, ReturnRequest,
                         StatusUpdate)
from app.security import require_admin, verify_internal_key

router = APIRouter(prefix="/inventory", tags=["inventory"])

CATALOG_URL = os.environ.get("CATALOG_URL", "http://catalog-service:8003")


@router.post("/copies", response_model=CopyOut, status_code=201)
def add_copy(body: CopyCreate, _=Depends(require_admin), db: Session = Depends(get_db)):
    """ADMIN only: register a physical copy. The book must exist in the Catalog service."""
    resp = call_service("GET", f"{CATALOG_URL}/books/{body.book_id}")
    if resp.status_code == 404:
        raise HTTPException(404, "That book does not exist in the catalogue.")
    if resp.status_code != 200:
        raise HTTPException(502, "Catalog service returned an unexpected response.")
    copy = BookCopy(book_id=body.book_id, barcode=body.barcode.strip(), shelf_location=body.shelf_location)
    db.add(copy)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A copy with this barcode already exists.") from None
    return copy


@router.get("/copies", response_model=Page[CopyOut])
def list_copies(
    book_id: int | None = None,
    status: str | None = Query(None, pattern="^(AVAILABLE|BORROWED|LOST|MAINTENANCE)$"),
    params: PageParams = Depends(),
    _=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """ADMIN only."""
    stmt = select(BookCopy).order_by(BookCopy.id)
    if book_id:
        stmt = stmt.where(BookCopy.book_id == book_id)
    if status:
        stmt = stmt.where(BookCopy.status == status)
    return paginate(db, stmt, params)


@router.patch("/copies/{copy_id}/status", response_model=CopyOut)
def set_copy_status(copy_id: int, body: StatusUpdate, _=Depends(require_admin), db: Session = Depends(get_db)):
    """ADMIN only: mark a copy LOST / MAINTENANCE / AVAILABLE again."""
    copy = db.get(BookCopy, copy_id)
    if not copy:
        raise HTTPException(404, "Copy not found.")
    copy.status = body.status
    db.commit()
    return copy


@router.get("/availability/{book_id}", response_model=AvailabilityOut)
def availability(book_id: int, db: Session = Depends(get_db)):
    """Public: how many copies of a book exist and how many can be borrowed now."""
    total = db.scalar(select(func.count()).select_from(BookCopy).where(BookCopy.book_id == book_id)) or 0
    free = db.scalar(select(func.count()).select_from(BookCopy)
                     .where(BookCopy.book_id == book_id, BookCopy.status == "AVAILABLE")) or 0
    return AvailabilityOut(book_id=book_id, total_copies=total, available_copies=free)


# ---- internal endpoints: called by the Borrowing service only (X-Internal-Key) ----
@router.post("/internal/checkout", response_model=CopyOut, include_in_schema=False)
def internal_checkout(body: CheckoutRequest, _: None = Depends(verify_internal_key), db: Session = Depends(get_db)):
    copy = db.scalar(select(BookCopy).where(BookCopy.book_id == body.book_id, BookCopy.status == "AVAILABLE")
                     .order_by(BookCopy.id).limit(1).with_for_update(skip_locked=True))
    if not copy:
        raise HTTPException(409, "No copy of this book is available right now.")
    copy.status = "BORROWED"
    db.commit()
    return copy


@router.post("/internal/return", response_model=CopyOut, include_in_schema=False)
def internal_return(body: ReturnRequest, _: None = Depends(verify_internal_key), db: Session = Depends(get_db)):
    copy = db.get(BookCopy, body.copy_id)
    if not copy:
        raise HTTPException(404, "Copy not found.")
    copy.status = "AVAILABLE"
    db.commit()
    return copy
