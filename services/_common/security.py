"""JWT verification, role checks and the internal service-to-service key.

Every service verifies the token itself (the gateway checks it too), so a service
is still protected if someone calls its port directly.
"""
import hmac

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import get_settings

ADMIN = "ADMIN"
MEMBER = "MEMBER"

_bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: int
    role: str
    email: str = ""
    name: str = ""


def decode_token(token: str) -> CurrentUser:
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],  # explicit allow-list
            options={"require": ["exp", "sub", "iat"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token has expired.", headers={"WWW-Authenticate": "Bearer"}) from None
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token.", headers={"WWW-Authenticate": "Bearer"}) from None
    if claims.get("type") != "access":
        raise HTTPException(401, "Invalid token.", headers={"WWW-Authenticate": "Bearer"})
    return CurrentUser(
        id=int(claims["sub"]),
        role=str(claims.get("role", "")),
        email=str(claims.get("email", "")),
        name=str(claims.get("name", "")),
    )


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> CurrentUser:
    if creds is None:
        raise HTTPException(401, "Missing bearer token.", headers={"WWW-Authenticate": "Bearer"})
    return decode_token(creds.credentials)


def require_roles(*roles: str):
    """Dependency factory: only users whose JWT role is in `roles` may continue."""

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(403, f"This action requires one of the roles: {', '.join(roles)}.")
        return user

    return dependency


require_admin = require_roles(ADMIN)
require_member = require_roles(MEMBER)


def ensure_owner_or_admin(user: CurrentUser, owner_id: int) -> None:
    if user.role != ADMIN and user.id != owner_id:
        raise HTTPException(403, "You can only access your own records.")


def verify_internal_key(x_internal_key: str | None = Header(default=None)) -> None:
    """Guards /internal endpoints that only other services may call."""
    expected = get_settings().internal_api_key
    if not expected or not x_internal_key or not hmac.compare_digest(x_internal_key, expected):
        raise HTTPException(403, "Internal endpoint.")
