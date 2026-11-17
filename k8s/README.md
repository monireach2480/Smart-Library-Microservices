# `k8s/` — Kubernetes manifests

Apply in order; `scripts/k8s-deploy.ps1` does it for you.

| File | Objects |
|---|---|
| `00-namespace.yaml` | Namespace `smart-library` |
| `01-configmap.yaml` | Service URLs, `LOG_DIR`, tuning values |
| `02-secret.example.yaml` | **Template.** Copy to `02-secret.yaml` (git-ignored) or run `scripts\k8s-make-secret.ps1` |
| `03-storage.yaml` | ReadWriteMany PersistentVolume + Claim for shared logs |
| `10-registration-service.yaml` | Deployment + ClusterIP Service, port 8001 |
| `11-login-service.yaml` | Deployment + ClusterIP Service, port 8002 |
| `12-catalog-service.yaml` | Deployment (**3 replicas**) + ClusterIP Service, port 8003 |
| `13-member-service.yaml` | Deployment + ClusterIP Service, port 8004 |
| `14-inventory-service.yaml` | Deployment + ClusterIP Service, port 8005 |
| `15-borrowing-service.yaml` | Deployment + ClusterIP Service, port 8006 |
| `16-fine-service.yaml` | Deployment + ClusterIP Service, port 8007 |
| `17-review-service.yaml` | Deployment + ClusterIP Service, port 8008 |
| `20-gateway.yaml` | Gateway Deployment (**2 replicas** + `log-tailer` sidecar) + Service, port 8000 |
| `21-log-viewer.yaml` | Read-only viewer of the shared volume, port 8080 |
| `30-ingress.yaml` | Fanout DNS Ingress on `aupp.com`, `api.aupp.com`, `logs.aupp.com` |
| `40-networkpolicy.yaml` | Default-deny; backends reachable from the gateway only |

Full walkthrough: [../docs/KUBERNETES.md](../docs/KUBERNETES.md).
Guideline-by-guideline map: [../docs/RUBRIC_MAPPING.md](../docs/RUBRIC_MAPPING.md).

## Conventions

* Nothing is created imperatively — every object comes from a file here.
* Every microservice Service is `ClusterIP`; only the gateway is exposed, through the Ingress.
* No database runs in the cluster; `DATABASE_URL` points at a managed PostgreSQL instance.
* All application containers run as uid/gid 1000 with `fsGroup: 1000` so they can share the log volume.
* Images are `smart-library/<service>:1.0` with `imagePullPolicy: IfNotPresent`, built straight into
  Minikube's Docker daemon by `scripts\k8s-build-images.ps1`.

## Validating before applying

```powershell
kubectl apply -f k8s\ --dry-run=client
kubectl apply -f k8s\ --dry-run=server     # needs a running cluster; catches schema errors too
```
