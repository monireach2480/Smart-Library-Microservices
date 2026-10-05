from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Book
from app.pagination import Page, PageParams, paginate
from app.schemas import BookCreate, BookOut, BookUpdate, CategoryOut
from app.security import require_admin

router = APIRouter(tags=["catalog"])


@router.get("/books", response_model=Page[BookOut])
def search_books(
    q: str | None = Query(None, description="Search title, author, ISBN or description"),
    category: str | None = None,
    author: str | None = None,
    language: str | None = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    """Public: browse and search the catalogue."""
    stmt = select(Book).order_by(Book.title, Book.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Book.title.ilike(like), Book.author.ilike(like), Book.isbn.ilike(like),
                              Book.description.ilike(like)))
    if category:
        stmt = stmt.where(func.lower(Book.category) == category.strip().lower())
    if author:
        stmt = stmt.where(Book.author.ilike(f"%{author.strip()}%"))
    if language:
        stmt = stmt.where(func.lower(Book.language) == language.strip().lower())
    return paginate(db, stmt, params)


@router.get("/books/{book_id}", response_model=BookOut)
def get_book(book_id: int, db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found.")
    return book


@router.post("/books", response_model=BookOut, status_code=201)
def create_book(body: BookCreate, _=Depends(require_admin), db: Session = Depends(get_db)):
    """ADMIN only."""
    if db.scalar(select(Book.id).where(Book.isbn == body.isbn)):
        raise HTTPException(409, "A book with this ISBN already exists.")
    book = Book(**body.model_dump())
    db.add(book)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A book with this ISBN already exists.") from None
    return book


@router.put("/books/{book_id}", response_model=BookOut)
def update_book(book_id: int, body: BookUpdate, _=Depends(require_admin), db: Session = Depends(get_db)):
    """ADMIN only."""
    book = db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found.")
    clash = db.scalar(select(Book.id).where(Book.isbn == body.isbn, Book.id != book_id))
    if clash:
        raise HTTPException(409, "Another book already uses this ISBN.")
    for field, value in body.model_dump().items():
        setattr(book, field, value)
    db.commit()
    return book


@router.delete("/books/{book_id}", status_code=204)
def delete_book(book_id: int, _=Depends(require_admin), db: Session = Depends(get_db)):
    """ADMIN only."""
    book = db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found.")
    db.delete(book)
    db.commit()


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    """Public: every category with its number of books."""
    rows = db.execute(select(Book.category, func.count()).group_by(Book.category).order_by(Book.category)).all()
    return [CategoryOut(name=name, book_count=count) for name, count in rows]
