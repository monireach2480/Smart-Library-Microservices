#!/usr/bin/env python3
"""Copy the shared modules from services/_common into every service and (re)generate each
service's Dockerfile, requirements.txt and .dockerignore.

Every service folder must be self-contained so it can be built and deployed on its own EC2 instance.
Edit shared code ONLY in services/_common, then run:  python scripts/sync_common.py

Layout inside every service's app/ folder (shared files are copied to the same relative path):
    core/      config, database, security, observability, passwords, balancer      (shared)
    utils/     pagination (shared), isbn (catalog only)
    clients/   service_client - HTTP calls to other services with load balancing   (shared)
    models/    database tables        -> service specific (the users table is shared by 3 services)
    schemas/   request / response models -> service specific
    routers/   API endpoints          -> service specific
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "services"
COMMON = ROOT / "_common"

BASE = ["core/__init__.py", "core/config.py", "core/security.py"]
DB = BASE + ["core/database.py", "core/observability.py", "utils/__init__.py", "utils/pagination.py"]
PWD = ["core/passwords.py"]
CALLS = ["core/balancer.py", "clients/__init__.py", "clients/service_client.py"]
USERS = ["models/__init__.py", "models/user.py"]          # the shared `users` table

PIP_DB = ["sqlalchemy>=2.0.30,<2.1", "psycopg2-binary>=2.9.9"]
SERVICES = {
    # name: (port, shared files, extra pip packages)
    "gateway":              (8000, BASE + ["core/balancer.py"],              ["httpx>=0.27,<1.0"]),
    "registration-service": (8001, DB + PWD + USERS,                         PIP_DB + ["argon2-cffi>=23.1", "email-validator>=2.1"]),
    "login-service":        (8002, DB + PWD + USERS,                         PIP_DB + ["argon2-cffi>=23.1", "email-validator>=2.1"]),
    "catalog-service":      (8003, DB,                                       PIP_DB),
    "member-service":       (8004, DB + USERS,                               PIP_DB),
    "inventory-service":    (8005, DB + CALLS,                               PIP_DB + ["httpx>=0.27,<1.0"]),
    "borrowing-service":    (8006, DB + CALLS,                               PIP_DB + ["httpx>=0.27,<1.0"]),
    "fine-service":         (8007, DB,                                       PIP_DB),
    "review-service":       (8008, DB + CALLS,                               PIP_DB + ["httpx>=0.27,<1.0"]),
}
CORE = ["fastapi>=0.115,<1.0", "uvicorn[standard]>=0.30,<1.0", "pyjwt>=2.8,<3.0"]

DOCKERFILE = """FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT={port}
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --create-home app && chown -R app /srv
USER app
EXPOSE {port}
HEALTHCHECK --interval=20s --timeout=4s --start-period=25s --retries=3 \\\\
  CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ['PORT'], timeout=3)"]
CMD uvicorn app.main:app --host 0.0.0.0 --port ${{PORT}}
"""

HEADER = "# AUTO-COPIED from services/_common/{rel} - edit it there and run scripts/sync_common.py\n"

for name, (port, files, extra) in SERVICES.items():
    svc = ROOT / name
    app = svc / "app"
    app.mkdir(parents=True, exist_ok=True)
    (app / "__init__.py").touch()
    for rel in files:
        dest = app / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        body = (COMMON / rel).read_text()
        dest.write_text(HEADER.format(rel=rel) + body if body.strip() else "")
    (svc / "requirements.txt").write_text("\n".join(CORE + extra) + "\n")
    (svc / "Dockerfile").write_text(DOCKERFILE.format(port=port))
    (svc / ".dockerignore").write_text("__pycache__/\n*.pyc\n.env\n*.db\n")
    print(f"synced {name} (port {port})")
