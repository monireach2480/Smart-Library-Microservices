# Member 1 – repo owner

**You own:** `gateway` (common) · `catalog-service` · `member-service`
**Also yours (shared files):** `README.md`, `docker-compose.yml`, `.env.example`, `requirements-dev.txt`, `scripts/`, `tests/`, `postman/`, `docs/`, `services/_common/`, `deploy/postgres/`, `deploy/ec2-1-gateway-auth/`, `deploy/ec2-2-member1/`
**EC2:** #1 (gateway + registration + login + PostgreSQL) and #2 (catalog + member)

| Service | Port | DB | Endpoints |
|---|---|---|---|
| gateway | 8000 | – | `/api/*` proxy with JWT/role checks and **round-robin load balancing + failover**; `/health`, `/health/services`, `/lb/stats` |
| catalog-service (3 replicas) | 8003 / 8013 / 8023 | catalog_db | `GET/POST /books`, `GET/PUT/DELETE /books/{id}`, `GET /categories` – tables `books` + `categories` (FK) |
| member-service | 8004 | auth_db | `GET /members`, `/members/stats`, `GET/PUT /members/{id}`, `PATCH /members/{id}/status` |

## Push to GitHub (you go first)
1. Create an **empty** repo on GitHub (no README), e.g. `smart-library`, and add Member 2 and Member 3 as collaborators.
2. Unzip `smart-library-member1.zip`, then:
```bash
cd smart-library
git init -b main
git add .
git commit -m "Initial commit: shared files, gateway, catalog and member services"
git remote add origin https://github.com/<you>/smart-library.git
git push -u origin main
```
3. Tell the others the repo URL. Review and merge their pull requests.

## Your extra responsibilities
* Load balancing: `services/gateway`, `services/_common/core/balancer.py`, `docs/LOAD_BALANCING.md`, `tests/load_balancer_test.py`.
* Shared files and evidence: README, docs, `docker-compose.yml`, `scripts/collect_evidence.py`, `evidence/`.
* EC2 #2 runs **3 Catalog replicas** – see `deploy/ec2-2-member1/docker-compose.yml`.

## Run
Needs the other members' services to be merged first for the full system. Until then you can run what you have; once everything is merged: `pip install -r requirements-dev.txt && python scripts/run_local.py`.
