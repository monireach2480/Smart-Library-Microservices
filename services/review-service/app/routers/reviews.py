import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients import call_service
from app.core.database import get_db
from app.models import Review
from app.utils.pagination import Page, PageParams, paginate
from app.schemas import RatingSummary, ReviewCreate, ReviewOut, ReviewUpdate
from app.core.security import ADMIN, CurrentUser, get_current_user, require_member

router = APIRouter(prefix="/reviews", tags=["reviews"])

CATALOG_URL = os.environ.get("CATALOG_URL", "http://catalog-service:8003")


@router.post("", response_model=ReviewOut, status_code=201)
def create_review(body: ReviewCreate, current: CurrentUser = Depends(require_member), db: Session = Depends(get_db)):
    """MEMBER only: one review per book. The book must exist in the Catalog service."""
    resp = call_service("GET", CATALOG_URL, f"/books/{body.book_id}")
    if resp.status_code == 404:
        raise HTTPException(404, "That book does not exist in the catalogue.")
    if resp.status_code != 200:
        raise HTTPException(502, "Catalog service returned an unexpected response.")
    if db.scalar(select(Review.id).where(Review.book_id == body.book_id, Review.user_id == current.id)):
        raise HTTPException(409, "You have already reviewed this book. Edit your review instead.")
    review = Review(book_id=body.book_id, user_id=current.id, user_name=current.name or "Member",
                    rating=body.rating, comment=body.comment)
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "You have already reviewed this book.") from None
    return review


@router.get("", response_model=Page[ReviewOut])
def list_reviews(book_id: int | None = None, user_id: int | None = None, params: PageParams = Depends(),
                 db: Session = Depends(get_db)):
    """Public: reviews, newest first. Filter by book and/or reviewer."""
    stmt = select(Review).order_by(Review.id.desc())
    if book_id:
        stmt = stmt.where(Review.book_id == book_id)
    if user_id:
        stmt = stmt.where(Review.user_id == user_id)
    return paginate(db, stmt, params)


@router.get("/summary/{book_id}", response_model=RatingSummary)
def summary(book_id: int, db: Session = Depends(get_db)):
    """Public: average rating and 1-5 star distribution for a book."""
    rows = dict(db.execute(select(Review.rating, func.count()).where(Review.book_id == book_id)
                           .group_by(Review.rating)).all())
    count = sum(rows.values())
    avg = round(sum(r * n for r, n in rows.items()) / count, 2) if count else None
    return RatingSummary(book_id=book_id, review_count=count, average_rating=avg,
                         distribution={star: rows.get(star, 0) for star in range(1, 6)})


@router.put("/{review_id}", response_model=ReviewOut)
def update_review(review_id: int, body: ReviewUpdate, current: CurrentUser = Depends(require_member),
                  db: Session = Depends(get_db)):
    """MEMBER only: edit your own review."""
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(404, "Review not found.")
    if review.user_id != current.id:
        raise HTTPException(403, "You can only edit your own review.")
    review.rating = body.rating
    review.comment = body.comment
    db.commit()
    return review


@router.delete("/{review_id}", status_code=204)
def delete_review(review_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """The review's author or an ADMIN (moderation)."""
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(404, "Review not found.")
    if current.role != ADMIN and review.user_id != current.id:
        raise HTTPException(403, "You can only delete your own review.")
    db.delete(review)
    db.commit()
