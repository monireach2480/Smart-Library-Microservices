#!/usr/bin/env python3
"""Run all 9 services (Catalog as 3 replicas = 11 processes) on localhost with SQLite - no Docker, no PostgreSQL needed.

    pip install -r requirements-dev.txt
    python scripts/run_local.py          # gateway on http://localhost:8000

Stop with Ctrl+C. Databases are plain files in ./.local-data (delete the folder to reset).
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / ".local-data"
DATA.mkdir(exist_ok=True)

# label -> (service folder, port, database file).  The Catalog service runs as 3 replicas (load balancing demo).
SERVICES = {
    "registration-service": ("registration-service", 8001, "auth.db"),
    "login-service": ("login-service", 8002, "auth.db"),          # same auth database as registration + member
    "catalog-1": ("catalog-service", 8003, "catalog.db"),
    "catalog-2": ("catalog-service", 8013, "catalog.db"),
    "catalog-3": ("catalog-service", 8023, "catalog.db"),
    "member-service": ("member-service", 8004, "auth.db"),
    "inventory-service": ("inventory-service", 8005, "inventory.db"),
    "borrowing-service": ("borrowing-service", 8006, "borrowing.db"),
    "fine-service": ("fine-service", 8007, "fine.db"),
    "review-service": ("review-service", 8008, "review.db"),
    "gateway": ("gateway", 8000, None),
}

env_base = {
    **os.environ,
    "SECRET_KEY": os.environ.get("SECRET_KEY", "local-dev-secret-key-change-me-0123456789"),
    "INTERNAL_API_KEY": os.environ.get("INTERNAL_API_KEY", "local-internal-key-0123456789"),
    "ADMIN_REGISTRATION_KEY": os.environ.get("ADMIN_REGISTRATION_KEY", "local-admin-key"),
    "REGISTRATION_URL": "http://127.0.0.1:8001", "LOGIN_URL": "http://127.0.0.1:8002",
    "CATALOG_URL": "http://127.0.0.1:8003,http://127.0.0.1:8013,http://127.0.0.1:8023", "MEMBER_URL": "http://127.0.0.1:8004",
    "INVENTORY_URL": "http://127.0.0.1:8005", "BORROWING_URL": "http://127.0.0.1:8006",
    "FINE_URL": "http://127.0.0.1:8007", "REVIEW_URL": "http://127.0.0.1:8008",
}

procs: list[subprocess.Popen] = []


def stop(*_):
    for p in procs:
        p.terminate()
    sys.exit(0)


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

for label, (folder, port, db) in SERVICES.items():
    env = dict(env_base, INSTANCE_ID=label)
    if db:
        env["DATABASE_URL"] = f"sqlite:///{DATA / db}"
    procs.append(subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port),
         "--log-level", "warning"],
        cwd=ROOT / "services" / folder, env=env))
    print(f"started {label:22s} http://127.0.0.1:{port}")

print("\nGateway: http://127.0.0.1:8000   (docs: /docs, service status: /health/services)")
print("Admin sign-up key for local runs: X-Admin-Key: " + env_base["ADMIN_REGISTRATION_KEY"])
reported: set[int] = set()
while True:
    time.sleep(1)
    for p in procs:
        if p.poll() is not None and p.pid not in reported:
            reported.add(p.pid)
            print(f"WARNING: a service process (pid {p.pid}) exited with code {p.returncode} - the others keep running.")
    if all(p.poll() is not None for p in procs):
        print("All services exited.")
        sys.exit(0)
