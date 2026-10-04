# AUTO-COPIED from services/_common - edit it there and run scripts/sync_common.py
"""Tiny helper for service-to-service HTTP calls."""
import httpx
from fastapi import HTTPException

from app.config import get_settings


def call_service(method: str, url: str, *, json: dict | None = None, internal: bool = False,
                 timeout: float = 5.0) -> httpx.Response:
    headers = {"X-Internal-Key": get_settings().internal_api_key} if internal else {}
    try:
        return httpx.request(method, url, json=json, headers=headers, timeout=timeout)
    except httpx.RequestError:
        raise HTTPException(503, f"Upstream service unavailable: {url}") from None
