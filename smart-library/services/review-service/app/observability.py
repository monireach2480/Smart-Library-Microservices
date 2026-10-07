# AUTO-COPIED from services/_common - edit it there and run scripts/sync_common.py
"""Adds `X-Served-By: <service>/<instance>` and `X-Response-Time-ms` to every response, so it is visible
(in Postman or curl) WHICH replica handled a request. INSTANCE_ID defaults to the container hostname."""
import os
import socket
import time

from fastapi import FastAPI, Request

INSTANCE_ID = os.environ.get("INSTANCE_ID") or socket.gethostname()


def install(app: FastAPI, service: str) -> None:
    @app.middleware("http")
    async def add_instance_headers(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Served-By"] = f"{service}/{INSTANCE_ID}"
        response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
        return response
