#!/usr/bin/env python3
"""Copy the shared modules from services/_common into every service and (re)generate each
service's Dockerfile, requirements.txt and .dockerignore.

Every service folder must be self-contained so it can be built and deployed on its own EC2 instance.
Edit shared code ONLY in services/_common, then run:  python scripts/sync_common.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "services"
COMMON = ROOT / "_common"

BASE = ["config.py", "security.py"]
DB = BASE + ["database.py"]
PAGED = DB + ["pagination.py"]
PWD = DB + ["passwords.py"]

SERVICES = {
    # name: (port, shared files, users-table model?, extra pip packages)
    "gateway":              (8000, BASE,                      False, ["httpx>=0.27,<1.0"]),
    "registration-service": (8001, PWD,                       True,  ["sqlalchemy>=2.0.30,<2.1", "psycopg2-binary>=2.9.9", "argon2-cffi>=23.1", "email-validator>=2.1"]),
    "login-service":        (8002, PWD,                       True,  ["sqlalchemy>=2.0.30,<2.1", "psycopg2-binary>=2.9.9", "argon2-cffi>=23.1", "email-validator>=2.1"]),
    "catalog-service":      (8003, PAGED,                     False, ["sqlalchemy>=2.0.30,<2.1", "psycopg2-binary>=2.9.9"]),
    "member-service":       (8004, PAGED,                     True,  ["sqlalchemy>=2.0.30,<2.1", "psycopg2-binary>=2.9.9"]),
    "inventory-service":    (8005, PAGED + ["clients.py"],    False, ["sqlalchemy>=2.0.30,<2.1", "psycopg2-binary>=2.9.9", "httpx>=0.27,<1.0"]),
    "borrowing-service":    (8006, PAGED + ["clients.py"],    False, ["sqlalchemy>=2.0.30,<2.1", "psycopg2-binary>=2.9.9", "httpx>=0.27,<1.0"]),
    "fine-service":         (8007, PAGED,                     False, ["sqlalchemy>=2.0.30,<2.1", "psycopg2-binary>=2.9.9"]),
    "review-service":       (8008, PAGED + ["clients.py"],    False, ["sqlalchemy>=2.0.30,<2.1", "psycopg2-binary>=2.9.9", "httpx>=0.27,<1.0"]),
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
CMD uvicorn app.main:app --host 0.0.0.0 --port ${{PORT}}
"""

for name, (port, files, users_model, extra) in SERVICES.items():
    svc = ROOT / name
    app = svc / "app"
    app.mkdir(parents=True, exist_ok=True)
    (app / "__init__.py").touch()
    for f in files:
        header = "# AUTO-COPIED from services/_common - edit it there and run scripts/sync_common.py\n"
        (app / f).write_text(header + (COMMON / f).read_text())
    if users_model:
        header = "# AUTO-COPIED from services/_common/users_model.py - edit it there and run scripts/sync_common.py\n"
        (app / "models.py").write_text(header + (COMMON / "users_model.py").read_text())
    (svc / "requirements.txt").write_text("\n".join(CORE + extra) + "\n")
    (svc / "Dockerfile").write_text(DOCKERFILE.format(port=port))
    (svc / ".dockerignore").write_text("__pycache__/\n*.pyc\n.env\n*.db\n")
    print(f"synced {name} (port {port})")
