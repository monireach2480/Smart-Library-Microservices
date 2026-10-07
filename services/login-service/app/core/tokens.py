import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings
from app.models import User


def create_access_token(user: User) -> tuple[str, int]:
    """Signed JWT carrying the user's id (sub) and role. Returns (token, seconds_valid)."""
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "email": user.email,
        "name": user.name,
        "type": "access",
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
    }
    return jwt.encode(payload, s.secret_key, algorithm=s.jwt_algorithm), s.access_token_minutes * 60
