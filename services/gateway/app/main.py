"""API Gateway: the single public entry point.

* routes /api/... to the right microservice
* verifies the JWT and enforces coarse role rules before forwarding
* blocks every /internal endpoint from the outside
"""
import asyncio
import os
import re
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.security import ADMIN, decode_token

# ---- where each microservice lives (set these to the EC2 private IPs in production) ----
SERVICES: dict[str, str] = {
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
    """Pings every downstream microservice."""
    async def ping(name: str, url: str):
        try:
            r = await request.app.state.http.get(f"{url}/health", timeout=3.0)
            return name, ("up" if r.status_code == 200 else f"http {r.status_code}")
        except httpx.HTTPError:
            return name, "down"

    results = dict(await asyncio.gather(*(ping(n, u) for n, u in SERVICES.items())))
    return {"gateway": "up", "services": results}


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

    try:
        upstream = await request.app.state.http.request(
            method, SERVICES[service] + upstream_path, params=request.query_params,
            content=await request.body(), headers=headers,
        )
    except httpx.TimeoutException:
        return JSONResponse({"detail": f"{service} service timed out."}, status_code=504)
    except httpx.HTTPError:
        return JSONResponse({"detail": f"{service} service is unavailable."}, status_code=502)

    out_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=out_headers)
