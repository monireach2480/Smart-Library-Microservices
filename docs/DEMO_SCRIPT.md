# Live demonstration script (~10 minutes)

Have ready: the 4 EC2 instances running, Postman with the collection imported (`baseUrl` = `http://<EC2-1 public IP>:8000`, `adminKey` set), the architecture diagram (`docs/architecture.png`), a terminal with the repo.

| # | Minutes | Show | Say |
|---|---|---|---|
| 1 | 1 | `docs/architecture.png` | 9 microservices on 4 EC2 instances; only the gateway (8000) is public; one PostgreSQL, one database per service |
| 2 | 1 | `docker compose ps` on EC2 #1 and #2 (all *healthy*), `GET /health/services` | every container has a health check and restart policy; 3 Catalog replicas up |
| 3 | 2 | Postman folders **1 + 2**: register member, register admin (with / without `X-Admin-Key`), login → copy the JWT, `GET /auth/verify` | JWT carries the role; admin accounts need the secret key |
| 4 | 2 | Postman **RBAC** requests: *No token → 401*, *List members as MEMBER → 403*, *Add book as MEMBER → 403*, *ADMIN borrows → 403*, *internal endpoint → 403* | gateway rejects before forwarding; services re-check themselves |
| 5 | 2 | Folders **4 → 6 → 7**: admin adds a book, adds a copy, member borrows (availability drops), returns; show a fine (`GET /fines/{id}` with receipt) | borrowing calls member, inventory and fine services; each has its own database |
| 6 | 2 | Folder **9** with 30 iterations → console shows `catalog-1/2/3` alternating; `GET /lb/stats` | round-robin load balancing, evidence per replica |
| 7 | 1 | `docker compose stop catalog-service-2` on EC2 #2 → rerun folder 9 (still all 200, two replicas) → `/health/services` shows *degraded (2/3)* → `docker compose start catalog-service-2` | failover and automatic recovery |
| 8 | 1 | Open `evidence/` and `docs/DATABASE.md` | automated tests, schema, relationships |

**If something fails live:** `curl http://<gateway>:8000/health/services` tells which instance is down; `docker compose logs -f <service>` on that instance shows why.
