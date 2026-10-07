# AUTO-COPIED from services/_common - edit it there and run scripts/sync_common.py
"""Service-to-service HTTP calls with load balancing + failover over a service's replicas."""
import httpx
from fastapi import HTTPException

from app.balancer import UpstreamPool
from app.config import get_settings

_pools: dict[str, UpstreamPool] = {}
_IDEMPOTENT = {"GET", "HEAD", "OPTIONS"}


def _pool(bases: str) -> UpstreamPool:
    if bases not in _pools:
        _pools[bases] = UpstreamPool(bases)
    return _pools[bases]


def call_service(method: str, bases: str, path: str, *, json: dict | None = None, internal: bool = False,
                 timeout: float = 5.0) -> httpx.Response:
    """`bases` is one URL or a comma-separated list of replicas; `path` e.g. '/books/3'."""
    headers = {"X-Internal-Key": get_settings().internal_api_key} if internal else {}
    pool = _pool(bases)
    for base in pool.candidates():
        try:
            resp = httpx.request(method, base + path, json=json, headers=headers, timeout=timeout)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            pool.mark_down(base)          # request never reached the replica: always safe to retry elsewhere
            continue
        except httpx.RequestError:
            pool.mark_down(base)
            if method in _IDEMPOTENT:
                continue
            break                          # the call may have been processed: do not repeat it
        pool.record(base)
        return resp
    raise HTTPException(503, f"Upstream service unavailable: {bases}")
