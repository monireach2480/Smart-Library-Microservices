# AUTO-COPIED from services/_common/core/observability.py - edit it there and run scripts/sync_common.py
"""Response headers + shared access logging.

Two jobs:

1. Adds `X-Served-By: <service>/<instance>` and `X-Response-Time-ms` to every response, so it is visible
   (in Postman or curl) WHICH replica handled a request. INSTANCE_ID defaults to the container hostname.

2. Appends one JSON line per request to a SHARED log file (`$LOG_DIR/access.log`). In Kubernetes that
   directory is a ReadWriteMany PersistentVolume mounted into every service Pod, the log-tailer sidecar
   and the log-viewer Pod - so a single file is written by ~12 containers and read by others. Writes use
   O_APPEND with one `write()` per line, which the kernel keeps atomic for lines below PIPE_BUF (4 KiB),
   so interleaved writers do not corrupt each other's lines.

If LOG_DIR does not exist or is not writable (plain `docker compose up`, local `uvicorn`), file logging is
silently skipped and only the response headers are added. Nothing here can take a request down.
"""
import json
import os
import socket
import threading
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request

INSTANCE_ID = os.environ.get("INSTANCE_ID") or socket.gethostname()
LOG_DIR = os.environ.get("LOG_DIR", "")
LOG_FILE = os.path.join(LOG_DIR, os.environ.get("LOG_FILE", "access.log")) if LOG_DIR else ""

_lock = threading.Lock()          # serialises writes from the threads of ONE container
_fd: int | None = None            # file descriptor of the shared log, or None if logging is off


def _open_log() -> int | None:
    """Open the shared log file for appending. Returns None if the volume is absent or read-only."""
    if not LOG_FILE:
        return None
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        return os.open(LOG_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o664)
    except OSError as exc:        # no volume mounted, or mounted read-only: keep serving requests
        print(f"[observability] shared log disabled ({LOG_FILE}): {exc}", flush=True)
        return None


def write_event(service: str, event: str, **fields) -> None:
    """Append one JSON line to the shared log. Safe to call even when logging is off."""
    if _fd is None:
        return
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "service": service,
        "instance": INSTANCE_ID,
        "event": event,
        **fields,
    }
    line = (json.dumps(record, separators=(",", ":")) + "\n").encode()
    try:
        with _lock:
            os.write(_fd, line)   # single O_APPEND write: atomic across containers for short lines
    except OSError:
        pass                      # a full or disconnected volume must never break the API


def install(app: FastAPI, service: str) -> None:
    global _fd
    if _fd is None:
        _fd = _open_log()
    write_event(service, "startup", pid=os.getpid(), log_file=LOG_FILE or None)

    @app.middleware("http")
    async def add_instance_headers(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        # On a microservice this sets X-Served-By. On the gateway the response already carries the
        # upstream's X-Served-By (the replica that did the work, which is what the load-balancing
        # tests read), so the gateway records its own identity under X-Proxied-By instead of
        # overwriting it.
        if "X-Served-By" in response.headers:
            response.headers["X-Proxied-By"] = f"{service}/{INSTANCE_ID}"
        else:
            response.headers["X-Served-By"] = f"{service}/{INSTANCE_ID}"
        response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.1f}"
        write_event(
            service,
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=round(elapsed_ms, 1),
            # the gateway mints the id and stores it on request.state; downstream services
            # receive it as a header. Either way both log lines share it, so a single request
            # can be followed across containers in the shared file.
            request_id=getattr(request.state, "request_id", None) or request.headers.get("x-request-id"),
        )
        return response

    @app.get("/ops/log-tail", tags=["ops"], include_in_schema=False)
    def log_tail(lines: int = 20):
        """Proof that this container can READ the same shared file every other container writes to."""
        if not LOG_FILE or not os.path.exists(LOG_FILE):
            return {"shared_log": LOG_FILE or None, "enabled": False, "lines": []}
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as fh:
            tail = fh.readlines()[-max(1, min(lines, 200)):]
        return {
            "shared_log": LOG_FILE,
            "enabled": True,
            "read_by": f"{service}/{INSTANCE_ID}",
            "lines": [ln.rstrip("\n") for ln in tail],
        }
