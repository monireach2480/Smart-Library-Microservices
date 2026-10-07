# Load balancing

## What is load-balanced
The **API Gateway is the load balancer.** For every downstream service it holds a *pool* of instance URLs and distributes requests over them round-robin. Any service can be scaled by listing more URLs; the demonstration uses the **Catalog service with 3 replicas** (it is stateless and read-heavy – all replicas share `catalog_db`).

```
                       ┌─ catalog-1 :8003  (X-Served-By: catalog-service/catalog-1)
Client ─► Gateway :8000 ┼─ catalog-2 :8013  (X-Served-By: catalog-service/catalog-2)
          round-robin   └─ catalog-3 :8023  (X-Served-By: catalog-service/catalog-3)
```
The same pool logic (`services/_common/core/balancer.py`) is used by the services that call Catalog (Inventory, Review), so internal traffic is balanced too.

## How it works
| Feature | Behaviour |
|---|---|
| **Algorithm** | Round-robin over the instances that are currently healthy |
| **Configuration** | A comma-separated list in the service URL variable, e.g. `CATALOG_URL=http://a:8003,http://b:8013,http://c:8023` |
| **Failover** | If an instance refuses the connection it is taken out of rotation for 10 s and the request is **retried on the next instance** – the client never sees the error |
| **Safe retries** | Connection failures are retried for every method (the request never reached the instance). Timeouts are retried only for `GET/HEAD`, so a `POST` is never executed twice |
| **Recovery** | After the 10 s cooldown the gateway probes the instance again; once it answers it rejoins the rotation automatically |
| **Visibility** | Every service adds `X-Served-By: <service>/<instance>`; the gateway adds `X-Upstream: <url>` and `X-Request-ID`. `GET /health/services` lists every instance; `GET /lb/stats` (ADMIN) shows requests and failures per instance |

## Where the replicas are defined
| Environment | File | Replicas |
|---|---|---|
| Local, no Docker | `scripts/run_local.py` | 3 processes, ports 8003 / 8013 / 8023 |
| Docker Compose | `docker-compose.yml` | `catalog-service-1/2/3` |
| EC2 | `deploy/ec2-2-member1/docker-compose.yml` | 3 containers on EC2 #2 (host ports 8003 / 8013 / 8023); gateway, inventory and review list all three URLs |

To add a 4th replica: add one more container with a new host port and append its URL to `CATALOG_URL` in the gateway, inventory and review settings.

## How to verify (evidence)
**1. Automated test** – 60 sequential + 60 concurrent requests, counts which replica answered:
```bash
python tests/load_balancer_test.py                                            # local
python tests/load_balancer_test.py http://<EC2-1 public IP>:8000 --admin-key <ADMIN_REGISTRATION_KEY>
```
Expected: `catalog-1: 20, catalog-2: 20, catalog-3: 20` and `LOAD BALANCING VERIFIED`.

**2. Postman** – open folder **9 – Load balancing**, right-click → *Run folder*, set **Iterations = 30**. The console prints `X-Served-By` for each call and the running totals. Then run folder **10** to see the gateway's own counters (`/lb/stats`).

**3. curl** – watch the header change:
```bash
for i in 1 2 3 4 5 6; do curl -s -D - -o /dev/null "http://<gateway>:8000/api/books?page_size=1" | grep -i x-served-by; done
```

**4. Failover demo** (do this live):
```bash
docker compose stop catalog-service-2                         # run in the compose folder (root, or deploy/ec2-2-member1 on EC2 #2)
python tests/load_balancer_test.py --expect 2                 # every request still returns 200, only 2 replicas serve
curl http://<gateway>:8000/health/services                    # catalog: "degraded (2/3 instances up)"
docker compose start catalog-service-2                        # wait ~10 s ...
python tests/load_balancer_test.py --expect 3                 # back to 3 replicas
```
Saved results of exactly this scenario: `evidence/sample-local-run/failover_test.txt`.
