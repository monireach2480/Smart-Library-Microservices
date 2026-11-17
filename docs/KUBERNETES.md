# Kubernetes deployment

The whole system runs on Kubernetes from **YAML configuration files only** — `kubectl apply -f k8s/`.
No Helm charts, no `kubectl create deployment`, no imperative object creation.

```
Internet / browser / Postman
            |
            v
   Ingress  "smart-library-fanout"          <-- fanout DNS on aupp.com
   +-----------------------------------+
   | aupp.com/        -> gateway       |
   | aupp.com/api/... -> gateway       |
   | aupp.com/logs/   -> log-viewer    |
   | api.aupp.com     -> gateway       |
   | logs.aupp.com    -> log-viewer    |
   +-----------------------------------+
            |
            v
   Service gateway (ClusterIP)  -- 2 Pods, each with a log-tailer sidecar
            |
            |  (the ONLY way in: every microservice Service is ClusterIP,
            |   no Ingress rule points at one, NetworkPolicy blocks the rest)
            v
 +---------+---------+---------+---------+---------+---------+---------+
 | registr | login   | catalog | member  | invent  | borrow  | fine    | review
 |  :8001  |  :8002  | :8003x3 |  :8004  |  :8005  |  :8006  |  :8007  | :8008
 +----+----+----+----+----+----+----+----+----+----+----+----+----+----+---+
      |         |         |         |         |         |         |       |
      +---------+---------+----+----+---------+---------+---------+-------+
                                |                        |
                                v                        v
                  Cloud PostgreSQL (Neon/RDS)   PersistentVolume "shared-logs"
                  6 databases, TLS, no DB        RWX, mounted by 11 containers
                  container in the cluster
```

## Files

| File | What it creates |
|---|---|
| `k8s/00-namespace.yaml` | Namespace `smart-library` |
| `k8s/01-configmap.yaml` | Service URLs, `LOG_DIR`, application tuning |
| `k8s/02-secret.example.yaml` | Template for `SECRET_KEY`, the internal key, and the six cloud `DATABASE_URL`s |
| `k8s/03-storage.yaml` | `PersistentVolume` + `PersistentVolumeClaim` (ReadWriteMany) for shared logs |
| `k8s/10…17-*.yaml` | A `Deployment` + ClusterIP `Service` for each of the 8 microservices |
| `k8s/20-gateway.yaml` | Gateway `Deployment` (2 replicas, + `log-tailer` sidecar) and `Service` |
| `k8s/21-log-viewer.yaml` | Read-only viewer of the shared volume, served at `logs.aupp.com` |
| `k8s/30-ingress.yaml` | The fanout DNS `Ingress` on `aupp.com` |
| `k8s/40-networkpolicy.yaml` | Default-deny + "backends reachable from the gateway only" |

30 objects in total: 10 Deployments (13 Pods), 10 Services, 1 Ingress, 4 NetworkPolicies, 1 PV, 1 PVC,
1 ConfigMap, 1 Secret, 1 Namespace.

## Prerequisites

* Docker Desktop
* `minikube` and `kubectl` on `PATH`
* A cloud PostgreSQL database — see [deploy/cloud-db/README.md](../deploy/cloud-db/README.md)

## Deploy — PowerShell, start to finish

```powershell
# 1. Start the cluster. --cni=calico makes the NetworkPolicies actually enforced.
minikube start --cpus=4 --memory=6144 --cni=calico
minikube addons enable ingress

# 2. Build the nine images inside Minikube's Docker daemon
.\scripts\k8s-build-images.ps1

# 3. Create the cloud databases (once), then generate the Secret
#    Run deploy/cloud-db/init-cloud-databases.sql on Neon/RDS first.
.\scripts\k8s-make-secret.ps1

# 4. Apply every manifest and wait for the rollout
.\scripts\k8s-deploy.ps1

# 5. Point aupp.com at the cluster  (ADMINISTRATOR PowerShell)
.\scripts\k8s-setup-dns.ps1

# 6. Check every guideline and save the evidence
.\scripts\k8s-verify.ps1
```

If Minikube uses the **Docker driver** on Windows, `minikube ip` is not routable from the host. Open a
second Administrator window, leave `minikube tunnel` running, and register `127.0.0.1` instead:

```powershell
minikube tunnel                              # leave this running
.\scripts\k8s-setup-dns.ps1 -ClusterIp 127.0.0.1
```

## Try it

```powershell
curl.exe http://aupp.com/health
curl.exe http://aupp.com/health/services         # every Pod of every service
curl.exe http://api.aupp.com/api/books
curl.exe http://logs.aupp.com/                   # the shared log directory

# a microservice is NOT reachable directly - this must fail
curl.exe http://aupp.com/api/../books            # 404 at the gateway, never a direct hit
kubectl -n smart-library get svc                 # every type is ClusterIP
```

Register an admin and borrow a book exactly as in [DEMO_SCRIPT.md](DEMO_SCRIPT.md), replacing
`http://localhost:8000` with `http://aupp.com`.

## Load balancing

Catalog runs **3 Pods** behind one ClusterIP Service. kube-proxy spreads connections across them, and
the `X-Served-By` header names the Pod that answered:

```powershell
1..20 | ForEach-Object { (curl.exe -s -D - -o NUL http://aupp.com/api/books | Select-String "X-Served-By") } |
    Group-Object | Format-Table Count, Name
```

Kill one and watch Kubernetes replace it while requests keep succeeding:

```powershell
kubectl -n smart-library delete pod -l app=catalog-service --field-selector status.phase=Running --wait=$false
kubectl -n smart-library get pods -l app=catalog-service -w
```

Scaling is still a YAML change — edit `replicas` in `k8s/12-catalog-service.yaml` and re-apply.

## The shared log volume

Every application container appends one JSON line per request to
`/var/log/smartlibrary/access.log` on a single ReadWriteMany volume (see
`services/_common/core/observability.py`). Eleven containers mount it: nine services, the gateway, its
`log-tailer` sidecar, and the `log-viewer` Pod.

```powershell
# which containers wrote to the one file
kubectl -n smart-library exec deploy/log-viewer -- `
  sh -c "cat /var/log/smartlibrary/access.log | grep -o '\`"instance\`":\`"[^\`"]*' | sort -u"

# the same file read from three different Pods
kubectl -n smart-library exec deploy/gateway -c gateway        -- wc -l /var/log/smartlibrary/access.log
kubectl -n smart-library exec deploy/catalog-service           -- wc -l /var/log/smartlibrary/access.log
kubectl -n smart-library exec deploy/log-viewer                -- wc -l /var/log/smartlibrary/access.log

# the sidecar streaming traffic produced by every other Pod
kubectl -n smart-library logs deploy/gateway -c log-tailer -f
```

Any service also exposes `/ops/log-tail`, which reads the shared file from inside that container.

## Deploying on EC2 instead of Minikube

Minikube runs fine on a single `t3.large` (2 vCPU / 8 GB):

```bash
sudo yum install -y docker && sudo systemctl enable --now docker && sudo usermod -aG docker ec2-user
curl -Lo minikube https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube /usr/local/bin/ && rm minikube
curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/ && rm kubectl
minikube start --driver=docker --cpus=2 --memory=6144
minikube addons enable ingress
```

Then clone the repo, build the images, apply `k8s/`, and expose the ingress controller on port 80:

```bash
kubectl -n ingress-nginx patch svc ingress-nginx-controller -p '{"spec":{"type":"NodePort"}}'
sudo socat TCP-LISTEN:80,fork TCP:$(minikube ip):$(kubectl -n ingress-nginx get svc ingress-nginx-controller -o jsonpath='{.spec.ports[0].nodePort}') &
```

Open port 80 in the security group, point an A record for `aupp.com` (or a hosts-file entry on your
laptop) at the instance's public IP, and allow 5432 from the instance to the RDS security group only.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Pods stuck `ImagePullBackOff` | Images were built on the host, not in Minikube. Re-run `.\scripts\k8s-build-images.ps1`. |
| Pods `CrashLoopBackOff`, logs show `RuntimeError: SECRET_KEY` | `k8s/02-secret.yaml` still has the placeholder. Re-run `k8s-make-secret.ps1`. |
| Pods `CrashLoopBackOff`, logs show `could not translate host name` | Wrong `DATABASE_URL`, or the cloud database blocks the cluster's IP. |
| `connection ... SSL off` | Append `?sslmode=require` to the `DATABASE_URL`. |
| `http://aupp.com` returns nothing | `minikube addons enable ingress`, then re-run `k8s-setup-dns.ps1`; with the Docker driver you also need `minikube tunnel`. |
| `Permission denied: /var/log/smartlibrary/access.log` | The Pod lacks `fsGroup: 1000`. All manifests set it; check you did not edit it out. |
| NetworkPolicies have no effect | Minikube's default CNI ignores them. `minikube delete` and start with `--cni=calico`. |
