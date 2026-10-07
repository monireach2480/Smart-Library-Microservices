# Testing and evidence

Three layers of automated tests; all of them run through the **API Gateway**, exactly like a real client.

| Test | Command | What it proves |
|---|---|---|
| **End-to-end API test** | `python tests/smoke_test.py [url] [--admin-key K]` | ~75 checks over all 9 services: registration, JWT login, every role rule (401/403), validation (422/409), CRUD in every service, borrowing → inventory → fine flow, receipts, suspension. Re-runnable on a live system |
| **Load-balancing test** | `python tests/load_balancer_test.py [url] [--expect N]` | traffic is spread evenly over the replicas, concurrent clients too, gateway counters list every replica; with `--expect 2` after stopping a replica it proves failover |
| **Postman collection** | `postman/SmartLibrary.postman_collection.json` | 66 requests in 11 folders (one per service + load balancing). Every request carries an assertion on its status code (e.g. "expect 403"), so *Run collection* is a pass/fail test |

## Run them
```bash
# local (no Docker)
pip install -r requirements-dev.txt
python scripts/run_local.py                 # terminal 1
python scripts/collect_evidence.py          # terminal 2 – runs everything and saves the output

# on EC2 / Docker
python scripts/collect_evidence.py http://<EC2-1 public IP>:8000 --admin-key <ADMIN_REGISTRATION_KEY>
```
`collect_evidence.py` writes `evidence/<timestamp>/` containing `SUMMARY.md`, `smoke_test.txt`, `load_balancer_test.txt`, `health_services.json` and – if Newman is installed (`npm install -g newman`) – `newman.txt`.
For screenshots of Postman, run the collection with **Runner** and capture the result screen plus folder 9's console.

## Saved evidence
`evidence/sample-local-run/` contains the real output of these tests from a run of the full system (all services, 3 Catalog replicas; SQLite instead of PostgreSQL):

| File | Content |
|---|---|
| `SUMMARY.md` | overall result |
| `smoke_test.txt` | every API check with its HTTP status |
| `load_balancer_test.txt` | 20 / 20 / 20 distribution over the 3 replicas |
| `newman.txt` | Postman collection run |
| `newman_load_balancing_30_iterations.txt` | 30 iterations of folder 9 with `X-Served-By` per call |
| `failover_test.txt` | one replica stopped → 0 failed requests; restarted → 3 replicas again |

Produce your own evidence on the EC2 deployment before the demonstration – it replaces the sample.

## Manual checks worth showing
* `GET /health/services` – every instance up
* Postman: `No token → 401`, `MEMBER → 403` on admin routes
* `docker compose ps` – all containers `healthy`
