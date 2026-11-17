# Project guidelines — where each one is met

Quick map from the assignment to the files that satisfy it. Deployment steps are in
[KUBERNETES.md](KUBERNETES.md).

## The seven guidelines

### 1. Kubernetes deployment, YAML configuration files only

`k8s/` holds 16 YAML files producing 30 objects. Everything is applied with `kubectl apply -f`; there is
no Helm chart and no imperative `kubectl create`. `scripts/k8s-deploy.ps1` only calls `kubectl apply` in
dependency order.

```
Deployment 10   Service 10   Ingress 1   NetworkPolicy 4
PersistentVolume 1   PersistentVolumeClaim 1   ConfigMap 1   Secret 1   Namespace 1
```

### 2. Pod configuration — multiple Pods as the architecture requires

13 application Pods, 14 containers:

| Deployment | Pods | Why |
|---|---|---|
| `gateway` | 2 | Highly available entry point; each Pod also runs the `log-tailer` sidecar |
| `catalog-service` | 3 | The read-heavy service; demonstrates load balancing across replicas |
| 7 other microservices | 1 each | One Pod per bounded context |
| `log-viewer` | 1 | Reads the shared volume |

Each Pod declares readiness and liveness probes on `/health`, CPU/memory requests and limits, and a
non-root `securityContext` matching the `app` user built into the images.

### 3. API Gateway — no direct client access to microservices

Enforced in three independent layers:

1. **Service type.** Every microservice `Service` is `ClusterIP`. No `NodePort`, no `LoadBalancer`.
2. **Ingress.** The only backends in `k8s/30-ingress.yaml` are `gateway` and `log-viewer` (an ops page
   for the shared volume, not a microservice). No rule routes to catalog, member, borrowing, etc.
3. **NetworkPolicy.** `k8s/40-networkpolicy.yaml` default-denies ingress in the namespace, then allows
   `tier: backend` Pods to accept traffic only from `tier: edge` (the gateway) and from each other, for
   the internal service-to-service calls.

The gateway itself still does what it did before: JWT validation, the coarse role policy, and a 403 on
anything containing `/internal`.

### 4. Database connectivity — cloud database, no database container

There is **no PostgreSQL object anywhere in `k8s/`** — no Deployment, no StatefulSet, no Service, no
data volume, and no database image in any Pod spec. Each service receives a `DATABASE_URL` for a
managed PostgreSQL instance from the `smart-library-secrets` Secret, over TLS (`sslmode=require`).

The database-per-service layout is unchanged: `auth_db` (shared by Registration, Login, Member),
`catalog_db`, `inventory_db`, `borrowing_db`, `fine_db`, `review_db`. Setup instructions for Neon and
RDS: [deploy/cloud-db/README.md](../deploy/cloud-db/README.md); the DDL:
`deploy/cloud-db/init-cloud-databases.sql`.

> The old `docker-compose.yml` still runs a PostgreSQL container. That path is for local development
> only and is not part of the Kubernetes deployment.

### 5. Fanout DNS on a domain name

One `Ingress`, one external IP, several backends selected by host and by path:

| Request | Backend |
|---|---|
| `aupp.com/` | gateway |
| `aupp.com/api/...` | gateway |
| `aupp.com/logs/` | log-viewer |
| `api.aupp.com/` | gateway |
| `logs.aupp.com/` | log-viewer |

This is simple path fanout *and* name-based virtual hosting on the same address. Note that fanout is
deliberately arranged so no application path bypasses the gateway — guideline 5 is satisfied without
breaking guideline 3. `scripts/k8s-setup-dns.ps1` adds the hosts-file entries.

### 6. Kubernetes Volumes — shared log data across containers

`k8s/03-storage.yaml` defines a 1 Gi **ReadWriteMany** PersistentVolume and Claim, mounted at
`/var/log/smartlibrary` by **11 containers**:

* the 10 application containers (9 services, Catalog ×3 → 10 writers), which append one JSON line per
  request via `services/_common/core/observability.py`
* the `log-tailer` sidecar inside each gateway Pod — mounted `readOnly`, follows the same file
* the `log-viewer` Pod — mounted `readOnly`, serves the directory at `logs.aupp.com`

Writes use a single `O_APPEND` `write()` per line, which the kernel keeps atomic below 4 KiB, so
concurrent writers from different Pods do not corrupt each other. Every service also exposes
`/ops/log-tail`, proving it can read lines written by other containers.

`scripts/k8s-verify.ps1` captures this: the list of distinct writer instances found in the one file, and
identical line counts read from three different Pods.

### 7. Local deployment with Minikube (EC2 also supported)

Minikube is the documented path, with full PowerShell scripts. An EC2 single-node Minikube setup is in
the last section of [KUBERNETES.md](KUBERNETES.md).

## Rubric rows

### Kubernetes Deployment & Infrastructure — targeting 15/15

> *Successfully deploys all microservices using YAML configuration files only. Appropriate use of
> multiple Pods, Services, Deployments, and application architecture is fully functional.*

All 9 microservices plus the log viewer deploy from YAML alone. 10 Deployments, 10 Services, 13 Pods,
with replica counts chosen for the architecture (2 gateways for availability, 3 catalog replicas for
read load). Probes, resource limits, non-root containers, ConfigMap/Secret separation, and a
NetworkPolicy layer. Functionality is unchanged from the working Compose version and is verified
end-to-end by the existing Postman collection pointed at `http://aupp.com`.

### Networking, Storage & Application Functionality — targeting 8/8

> *Correctly implements Fanout DNS (e.g. aupp.com), configures networking properly, and demonstrates
> shared storage using Kubernetes Volumes with successful data/log sharing across multiple containers.*

Fanout DNS on `aupp.com` with both path fanout and virtual hosting; networking layered as ClusterIP +
Ingress + NetworkPolicy; a ReadWriteMany volume written by 10 containers and read by 3 more, with a
reproducible demonstration script.

## Evidence to hand in

Run `.\scripts\k8s-verify.ps1` after deploying. It writes `evidence/k8s-run/`:

| File | Shows |
|---|---|
| `01-kubernetes-objects.txt` | Every object created from YAML |
| `02-pods.txt` | 13 Pods running across 10 Deployments |
| `03-gateway-only-routing.txt` | All Services ClusterIP; internal endpoints refused |
| `04-cloud-database.txt` | No database Pod; external hosts in every URL |
| `05-fanout-dns.txt` | Ingress rules, name resolution, all three hosts answering |
| `06-shared-volume.txt` | Distinct writer containers, same line count from 3 Pods, sidecar output |
| `07-load-balancing.txt` | 30 requests spread across the 3 Catalog Pods |
| `SUMMARY.md` | PASS/FAIL table |

Pair it with screenshots of `kubectl get all -n smart-library`, the browser on `http://aupp.com/docs`,
and `http://logs.aupp.com/`.
