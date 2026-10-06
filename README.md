# Smart Library – Microservices Backend

A backend-only library system built as **9 microservices** (FastAPI + PostgreSQL + JWT), deployed on **4 EC2 instances** and tested with Postman. Team of 3.

## Requirement checklist

| # | Requirement | How this project meets it |
|---|---|---|
| 1 | ≥ 2 roles | `ADMIN` (librarian) and `MEMBER`, stored in the `users` table and carried in the JWT |
| 2 | API Gateway + Registration + Login, role-based JWT | `gateway`, `registration-service`, `login-service`. Login signs the JWT; the gateway **and** every service verify it and check the role |
| 3 | ≥ 2 extra microservices per member | 2 each → 6 services (table below) |
| 4 | Total microservices | 3 common + 3 × 2 = **9** |
| 5 | Backend only, with a database | No UI. PostgreSQL (one database per service, `auth_db` shared by the 3 user-related services) |
| 6 | ≥ 2–3 APIs per service, connected to the DB | Every service has 2–6 endpoints backed by the database (registration 2, login 4, all others 4–6) (see `docs/API.md`) |
| 7 | Different EC2 instances, Postman, max 3–4 | **4 EC2 instances**, one `docker-compose.yml` each (`deploy/`), Postman collection included |

## Architecture

```
                          Postman / client
                                 │  :8000  (only public port)
┌────────────────────────────────▼───────────────────────────────┐
│ EC2 #1   API Gateway ── Registration ── Login ── PostgreSQL    │
└───────┬───────────────────────┬──────────────────────┬─────────┘
        │                       │                      │      (private network, security-group only)
┌───────▼────────┐     ┌────────▼────────┐     ┌───────▼────────┐
│ EC2 #2         │     │ EC2 #3          │     │ EC2 #4         │
│ MEMBER 1       │     │ MEMBER 2        │     │ MEMBER 3       │
│ Catalog :8003  │     │ Inventory :8005 │     │ Fine   :8007   │
│ Member  :8004  │     │ Borrowing :8006 │     │ Review :8008   │
└────────────────┘     └─────────────────┘     └────────────────┘
```

| Service | Port | Owner | Database | What it does |
|---|---|---|---|---|
| `gateway` | 8000 | Member 1 (common) | – | Single entry point. Routes `/api/...`, checks JWT + role, blocks `/internal/*` |
| `registration-service` | 8001 | Member 2 (common) | `auth_db` | Sign-up (MEMBER; ADMIN only with the secret `X-Admin-Key`) |
| `login-service` | 8002 | Member 3 (common) | `auth_db` | Email + password → signed JWT; profile; token verify; change password |
| `catalog-service` | 8003 | Member 1 | `catalog_db` | Books: search, CRUD, ISBN validation, categories |
| `member-service` | 8004 | Member 1 | `auth_db` | List / search members, stats, update profile, suspend / re-activate |
| `inventory-service` | 8005 | Member 2 | `inventory_db` | Physical copies, availability, copy status |
| `borrowing-service` | 8006 | Member 2 | `borrowing_db` | Borrow / return, loan limits, overdue detection |
| `fine-service` | 8007 | Member 3 | `fine_db` | Late-return fines (automatic), manual fines, payment |
| `review-service` | 8008 | Member 3 | `review_db` | Ratings and reviews, per-book summary |

**Services talk to each other over HTTP** (shared `INTERNAL_API_KEY` header on `/internal/*` endpoints, which the gateway refuses to expose):
borrowing → member (is the account active?), borrowing → inventory (reserve / release a copy), borrowing → fine (late fee), inventory → catalog and review → catalog (does the book exist?).

### Security model
* **Roles in the JWT** (`ADMIN` / `MEMBER`). The gateway rejects missing/invalid tokens and admin-only routes early; each service independently re-verifies the token and the role, so calling a service port directly is still safe.
* Passwords hashed with **Argon2id**; login timing does not reveal whether an email exists; suspended accounts cannot log in or borrow.
* The same `SECRET_KEY` is configured on every instance so any service can verify a token issued by the Login service.
* Only the gateway (`:8000`) needs to be reachable from the internet.

## Run it

### Option A – no Docker (fastest, uses SQLite)
```bash
pip install -r requirements-dev.txt
python scripts/run_local.py          # starts all 9 services, gateway on http://localhost:8000
python tests/smoke_test.py           # in a 2nd terminal: 60+ end-to-end checks through the gateway
```

### Option B – Docker Compose (all services + PostgreSQL on one machine)
```bash
cp .env.example .env                 # fill in the secrets
docker compose up --build
python tests/smoke_test.py http://localhost:8000 --admin-key <ADMIN_REGISTRATION_KEY>
```

### Option C – the real deployment on 4 EC2 instances
See **[docs/EC2_DEPLOYMENT.md](docs/EC2_DEPLOYMENT.md)**.

## Test with Postman
1. Import `postman/SmartLibrary.postman_collection.json`.
2. Collection variables: `baseUrl` = `http://<EC2-1 public IP>:8000` and `adminKey` = your `ADMIN_REGISTRATION_KEY`.
3. Right-click the collection → **Run**. Folders 0–8 run in order (one folder per service); tokens and ids are saved automatically.
   Requests marked *(expect 403 / 401 / 409 / 422)* demonstrate role-based access and validation.

## Team split (who owns what)
| Member | Common service | Own services | EC2 folder |
|---|---|---|---|
| **Member 1** (repo owner, also owns shared files) | `gateway` | `catalog-service`, `member-service` | `deploy/ec2-1-gateway-auth`, `deploy/ec2-2-member1` |
| **Member 2** | `registration-service` | `inventory-service`, `borrowing-service` | `deploy/ec2-3-member2` |
| **Member 3** | `login-service` | `fine-service`, `review-service` | `deploy/ec2-4-member3` |

Per-member guides: `docs/members/member-1.md`, `member-2.md`, `member-3.md`.

## Project layout
```
services/
  _common/            shared code (JWT/roles, DB, pagination, HTTP client) – edit here, then run scripts/sync_common.py
  gateway/  registration-service/  login-service/
  catalog-service/  member-service/                (Member 1)
  inventory-service/  borrowing-service/           (Member 2)
  fine-service/  review-service/                   (Member 3)
deploy/               one docker-compose.yml + .env.example per EC2 instance, PostgreSQL init script
postman/              Postman collection
scripts/              run_local.py, sync_common.py
tests/smoke_test.py   end-to-end test through the gateway
docs/                 API.md, EC2_DEPLOYMENT.md
```
Each service folder is self-contained (own `Dockerfile`, `requirements.txt`, `app/`), so it can be built and deployed on its own instance.

## Configuration (environment variables)
| Variable | Used by | Meaning |
|---|---|---|
| `SECRET_KEY` | all | JWT signing key, ≥ 32 chars, **identical everywhere** |
| `INTERNAL_API_KEY` | member, inventory, borrowing, fine | secret for service-to-service calls, identical everywhere |
| `ADMIN_REGISTRATION_KEY` | registration | needed in `X-Admin-Key` to create an ADMIN |
| `DATABASE_URL` | all except gateway | e.g. `postgresql+psycopg2://user:pw@host:5432/catalog_db` |
| `*_URL` (`CATALOG_URL`, `MEMBER_URL`, …) | gateway, inventory, borrowing, review | where the other services live |
| `LOAN_DAYS`, `MAX_ACTIVE_LOANS` | borrowing | default 14 days, 5 loans |
| `FINE_PER_DAY`, `MAX_FINE` | fine | default 0.50 per day, capped at 25.00 |
| `ACCESS_TOKEN_MINUTES` | login | default 60 |
