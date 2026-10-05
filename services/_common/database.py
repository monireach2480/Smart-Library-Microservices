"""SQLAlchemy engine/session. DATABASE_URL decides the database (PostgreSQL on EC2, SQLite for quick local runs)."""
import time
from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


_url = get_settings().database_url
if not _url:
    raise RuntimeError("DATABASE_URL is not set.")
engine = create_engine(
    _url,
    **({"connect_args": {"check_same_thread": False}} if _url.startswith("sqlite") else {"pool_pre_ping": True}),
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db


def init_db(retries: int = 30, delay: float = 2.0) -> None:
    """Create tables. Retries because the database container may still be starting, or another
    service sharing this database may be creating the same table at the same moment."""
    import app.models  # noqa: F401  (registers the tables on Base.metadata)

    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(engine)
            return
        except SQLAlchemyError:
            if attempt == retries:
                raise
            time.sleep(delay)
