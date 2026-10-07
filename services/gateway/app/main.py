"""API Gateway: the single public entry point.

* routes /api/... to the right microservice
* load-balances (round-robin + failover) across the replicas of a service
* verifies the JWT and enforces coarse role rules before forwarding
* blocks every /internal endpoint from the outside
"""
import asyncio
import os
import re
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.core.balancer import UpstreamPool
from app.core.security import ADMIN, decode_token

# ---- where each microservice lives. A value may list several replicas, comma-separated:
#      CATALOG_URL=http://10.0.0.5:8003,http://10.0.0.5:8013,http://10.0.0.5:8023 ----
SERVICE_URLS: dict[str, str] = {
    "registration": os.environ.get("REGISTRATION_URL", "http://registration-service:8001"),
    "login": os.environ.get("LOGIN_URL", "http://login-service:8002"),
    "catalog": os.environ.get("CATALOG_URL", "http://catalog-service:8003"),
    "member": os.environ.get("MEMBER_URL", "http://member-service:8004"),
    "inventory": os.environ.get("INVENTORY_URL", "http://inventory-service:8005"),
    "borrowing": os.environ.get("BORROWING_URL", "http://borrowing-service:8006"),
    "fine": os.environ.get("FINE_URL", "http://fine-service:8007"),
    "review": os.environ.get("REVIEW_URL", "http://review-service:8008"),
}

# (public path prefix, service, part of the path stripped before forwarding). Most specific first.
ROUTES: list[tuple[str, str, str]] = [
    ("/api/auth/register", "registration", "/api/auth"),
    ("/api/auth/check-email", "registration", "/api/auth"),
    ("/api/auth", "login", "/api/auth"),
    ("/api/books", "catalog", "/api"),
    ("/api/categories", "catalog", "/api"),
    ("/api/members", "member", "/api"),
    ("/api/inventory", "inventory", "/api"),
    ("/api/loans", "borrowing", "/api"),
    ("/api/fines", "fine", "/api"),
    ("/api/reviews", "review", "/api"),
]

READ = {"GET", "HEAD", "OPTIONS"}
WRITE = {"POST", "PUT", "PATCH", "DELETE"}
ANY = READ | WRITE

# (methods, regex on path, access). First match wins.  public = no token, auth = any valid token, admin = ADMIN role.
# Services re-check roles themselves (e.g. "MEMBER only", "owner or admin"); this is the first line of defence.
POLICY: list[tuple[set[str], str, str]] = [
    ({"POST"}, r"^/api/auth/(register|login)$", "public"),
    ({"GET"}, r"^/api/auth/check-email$", "public"),
    (READ, r"^/api/(books|categories)(/.*)?$", "public"),
    (READ, r"^/api/inventory/availability/\d+$", "public"),
    (READ, r"^/api/reviews(/.*)?$", "public"),
    (WRITE, r"^/api/books(/.*)?$", "admin"),
    (ANY, r"^/api/inventory(/.*)?$", "admin"),  # (availability is matched above)
    ({"GET"}, r"^/api/members/?$", "admin"),
    (ANY, r"^/api/members/stats$", "admin"),
    (ANY, r"^/api/members/\d+/status$", "admin"),
    ({"GET"}, r"^/api/loans/?$", "admin"),
    (ANY, r"^/api/fines/?$", "admin"),
]

POOLS: dict[str, UpstreamPool] = {name: UpstreamPool(urls) for name, urls in SERVICE_URLS.items()}
IDEMPOTENT = {"GET", "HEAD", "OPTIONS"}

HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
              "transfer-encoding", "upgrade", "host", "content-length", "content-encoding"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0))
    yield
    await app.state.http.aclose()


app = FastAPI(title="Smart Library API Gateway", version="1.0.0", lifespan=lifespan)


def resolve(path: str) -> tuple[str, str] | None:
    for prefix, service, strip in ROUTES:
        if path == prefix or path.startswith(prefix + "/"):
            return service, path[len(strip):]
    return None


def required_access(method: str, path: str) -> str:
    for methods, pattern, access in POLICY:
        if method in methods and re.match(pattern, path):
            return access
    return "auth"


@app.get("/", tags=["ops"])
def root():
    return {"service": "api-gateway", "docs": "/docs", "routes": sorted({r[0] for r in ROUTES})}


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok", "service": "api-gateway"}


@app.get("/health/services", tags=["ops"])
async def services_health(request: Request):
    """Pings every instance of every downstream microservice."""
    async def ping(name: str, url: str):
        try:
            r = await request.app.state.http.get(f"{url}/health", timeout=3.0)
            return name, url, ("up" if r.status_code == 200 else f"http {r.status_code}")
        except httpx.HTTPError:
            return name, url, "down"

    checks = await asyncio.gather(*(ping(n, u) for n, p in POOLS.items() for u in p.urls))
    instances: dict[str, dict[str, str]] = {n: {} for n in POOLS}
    for name, url, state in checks:
        instances[name][url] = state
    summary = {}
    for name, states in instances.items():
        up = sum(1 for v in states.values() if v == "up")
        summary[name] = "up" if up == len(states) and up == 1 else (
            f"up ({up}/{len(states)} instances)" if up == len(states) else
            ("down" if up == 0 else f"degraded ({up}/{len(states)} instances up)"))
    return {"gateway": "up", "services": summary, "instances": instances}


@app.get("/lb/stats", tags=["ops"])
async def lb_stats(request: Request):
    """ADMIN only: how many requests the gateway sent to each instance (evidence of load balancing)."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer ") or not auth[7:].strip():
        raise HTTPException(401, "Missing bearer token.", headers={"WWW-Authenticate": "Bearer"})
    if decode_token(auth[7:].strip()).role != ADMIN:
        raise HTTPException(403, "This route requires the ADMIN role.")
    return {name: pool.snapshot() for name, pool in POOLS.items()}


@app.api_route("/api/{rest:path}", methods=sorted(ANY), tags=["proxy"], include_in_schema=False)
async def proxy(request: Request, rest: str):
    path = "/api/" + rest
    method = request.method

    if "/internal" in path:
        raise HTTPException(403, "Internal endpoints are not exposed through the gateway.")

    target = resolve(path)
    if target is None:
        raise HTTPException(404, "Unknown route.")
    service, upstream_path = target
    if len(upstream_path) > 1:
        upstream_path = upstream_path.rstrip("/")

    access = required_access(method, path)
    if access != "public":
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer ") or not auth[7:].strip():
            raise HTTPException(401, "Missing bearer token.", headers={"WWW-Authenticate": "Bearer"})
        user = decode_token(auth[7:].strip())
        if access == "admin" and user.role != ADMIN:
            raise HTTPException(403, "This route requires the ADMIN role.")

    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP and k.lower() != "x-internal-key"}
    client_ip = request.client.host if request.client else ""
    headers["x-forwarded-for"] = (request.headers.get("x-forwarded-for", "") + ", " + client_ip).strip(", ")

    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    headers["x-request-id"] = request_id
    body = await request.body()
    pool = POOLS[service]
    upstream, used, failure = None, None, None
    for base in pool.candidates():
        try:
            upstream = await request.app.state.http.request(
                method, base + upstream_path, params=request.query_params, content=body, headers=headers)
            used = base
            break
        except (httpx.ConnectError, httpx.ConnectTimeout):
            pool.mark_down(base)           # never reached the instance: safe to retry on another one
            failure = 502
        except httpx.TimeoutException:
            pool.mark_down(base)
            failure = 504
            if method not in IDEMPOTENT:
                break                      # it may have been processed: do not repeat a write
        except httpx.HTTPError:
            pool.mark_down(base)
            failure = 502
            if method not in IDEMPOTENT:
                break
    if upstream is None:
        detail = f"{service} service timed out." if failure == 504 else f"{service} service is unavailable."
        return JSONResponse({"detail": detail}, status_code=failure or 502, headers={"X-Request-ID": request_id})
    pool.record(used)

    out_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP}
    out_headers["X-Upstream"] = used            # which instance the gateway chose
    out_headers["X-Request-ID"] = request_id
    return Response(content=upstream.content, status_code=upstream.status_code, headers=out_headers)
