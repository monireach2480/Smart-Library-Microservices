# AUTO-COPIED from services/_common/core/config.py - edit it there and run scripts/sync_common.py
"""Environment-driven settings shared by every service."""
import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    jwt_algorithm: str
    access_token_minutes: int
    internal_api_key: str


@lru_cache
def get_settings() -> Settings:
    secret = os.environ.get("SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("SECRET_KEY must be set and be at least 32 characters long.")
    return Settings(
        database_url=os.environ.get("DATABASE_URL", ""),
        secret_key=secret,
        jwt_algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
        access_token_minutes=int(os.environ.get("ACCESS_TOKEN_MINUTES", "60")),
        internal_api_key=os.environ.get("INTERNAL_API_KEY", ""),
    )
