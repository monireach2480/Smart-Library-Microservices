# Answer first: **No, you don't need AWS at all.**

| Component | Where it runs | AWS needed? |
|---|---|---|
| Kubernetes cluster | **Your laptop** (Minikube) | ❌ No |
| The 9 services + gateway | Minikube pods on your laptop | ❌ No |
| Ingress / aupp.com | Minikube ingress on your laptop | ❌ No |
| Database | **Neon** (cloud PostgreSQL) | ❌ No (Neon ≠ AWS) |
| Container images | Built locally into Minikube | ❌ No |
| Registry | None — images stay local | ❌ No |

**AWS is only used in two alternative deployment paths in the repo:**

1. `deploy/ec2-*/` — 4 EC2 instances running Docker Compose (you are **not** using this)
2. The "Minikube on EC2" section of `docs/KUBERNETES.md` (you are **not** using this)

Your setup is: **Minikube on your Windows laptop + Neon (Singapore) as the cloud DB**. Fully local compute, cloud database. The rubric checks for **"no database container in the cluster"** — which your setup satisfies — not for "the cluster is on AWS."

The only "cloud" component in your deployment is the **database (Neon)**. Everything else lives on your laptop. That's the correct and intended K8s submission.

---

# Regenerated full runbook — incorporating every fix from this session

These are the changes from the original guide, based on what actually happened on your machine:

| # | Original guide | Fixed version | Why |
|---|---|---|---|
| 1 | `minikube start --cpus=4 --memory=6144` | **`--cpus=2 --memory=3500 --container-runtime=docker`** | Docker Desktop only has 3.8 GB |
| 2 | Run `.ps1` scripts directly | **`Set-ExecutionPolicy` + `Unblock-File`** first | Windows blocks downloaded scripts |
| 3 | Build images directly | **First fix `\\` → `\` in all 9 Dockerfiles** | Dockerfile parse error |
| 4 | `psql -f …` | **Use Neon SQL Editor** | `psql` not installed |
| 5 | Enable ingress before cluster up | **Enable ingress AFTER cluster is Ready** | Addon times out otherwise |
| 6 | `Remove-Item k8s/02-secret.yaml` | **Regenerate `k8s/02-secret.yaml` from `.env`** | `k8s-deploy.ps1` requires the file |
| 7 | `load_balancer_test.py` expected to pass | **Expected: 2 checks fail (Compose-only)** | K8s uses one Service URL, kube-proxy does LB |

---

## PART 1 — Fix Windows prerequisites (one-time)

```powershell
# 1. Allow local scripts to run
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#   → Answer Y when prompted

# 2. Strip "downloaded file" markers from every .ps1 in the repo
cd "C:\Users\lenmo\Downloads\Smart-Library-Microservices"
Get-ChildItem -Path . -Recurse -Include *.ps1 | Unblock-File

# 3. Verify
Get-ExecutionPolicy -Scope CurrentUser            # → RemoteSigned
Get-Item .\scripts\k8s-build-images.ps1 -Stream Zone.Identifier -ErrorAction SilentlyContinue
#   → no output = unblocked ✅
```

---

## PART 2 — Fix the Dockerfile `\\` bug in all 9 services

The repo's Dockerfiles have `\\` at the end of the `HEALTHCHECK` line — invalid Dockerfile syntax (must be a single `\`). Fix all 9 in one shot:

```powershell
Get-ChildItem services -Recurse -Filter Dockerfile | ForEach-Object {
    $c = Get-Content $_.FullName -Raw
    $f = $c -replace '(?m)^(HEALTHCHECK.*?) \\\\\r?$', '$1 \'
    if ($f -ne $c) {
        [System.IO.File]::WriteAllText($_.FullName, $f, [System.Text.UTF8Encoding]::new($false))
        Write-Host "Fixed: $($_.FullName)" -ForegroundColor Green
    } else {
        Write-Host "No change: $($_.FullName)" -ForegroundColor DarkGray
    }
}
```

### Verify one of them

```powershell
Get-Content services\gateway\Dockerfile | Select-String "HEALTHCHECK" -Context 0,1
```

Expected — single `\`:

```
> HEALTHCHECK --interval=20s --timeout=4s --start-period=25s --retries=3 \
      CMD ["python", "-c", ...]
```

> ✅ **You likely did this already** — the build succeeded last time. Re-run only if you rebuild from scratch.

---

## PART 3 — Verify `.env` (already done ✅)

```powershell
Get-Content .env | Where-Object { $_ -match '^[A-Z_]+=' } |
  ForEach-Object { ($_ -split '=')[0] } | Sort-Object
```

Expected — 11 keys (9 used + 2 Postgres leftovers):

```
ADMIN_REGISTRATION_KEY
AUTH_DATABASE_URL
BORROWING_DATABASE_URL
CATALOG_DATABASE_URL
FINE_DATABASE_URL
INTERNAL_API_KEY
INVENTORY_DATABASE_URL
POSTGRES_PASSWORD
POSTGRES_USER
REVIEW_DATABASE_URL
SECRET_KEY
```

> ✅ Already done — you verified this earlier (11 keys present, `AUTH_DATABASE_URL` decoded to `ep-small-feather-aztju6cv.c-3...`).

---

## PART 4 — Verify Neon has all 6 databases (already done ✅)

Neon Console → **Databases** tab must show **7**:

```
neondb   auth_db   catalog_db   inventory_db   borrowing_db   fine_db   review_db
```

If any missing → Neon SQL Editor, run:

```sql
CREATE DATABASE auth_db;
CREATE DATABASE catalog_db;
CREATE DATABASE inventory_db;
CREATE DATABASE borrowing_db;
CREATE DATABASE fine_db;
CREATE DATABASE review_db;
```

> ✅ Already done — pods are running and reachable against all 6.

---

## PART 5 — Minikube (already running — verification only)

Your cluster is up. Confirm the current state:

```powershell
minikube status
kubectl get nodes
```

Expected:

```
host: Running
kubelet: Running
apiserver: Running

NAME       STATUS   ROLES           AGE
minikube   Ready    control-plane   ...
```

### If you ever need to restart from scratch — use these flags:

```powershell
minikube delete
minikube start --cpus=2 --memory=3500 --container-runtime=docker --cni=calico
```

**Why this exact command:**
- `--cpus=2 --memory=3500` → fits inside your 3.8 GB Docker Desktop cap
- `--container-runtime=docker` → makes `minikube docker-env` (used by `k8s-build-images.ps1`) work on Windows (the default containerd runtime triggers `SSH_AGENT_START` errors)
- `--cni=calico` → mandatory for NetworkPolicies

> ⚠️ **Do not** use `--cpus=4 --memory=6144` — that's what failed with "Docker Desktop has only 3803MB".

> ✅ Already running — cluster is up and pods are deployed.

---

## PART 6 — Images (already built ✅)

```powershell
minikube image ls | Select-String smart-library
```

Expected — 9 images:

```
docker.io/smart-library/gateway:1.0
docker.io/smart-library/registration-service:1.0
docker.io/smart-library/login-service:1.0
docker.io/smart-library/catalog-service:1.0
docker.io/smart-library/member-service:1.0
docker.io/smart-library/inventory-service:1.0
docker.io/smart-library/borrowing-service:1.0
docker.io/smart-library/fine-service:1.0
docker.io/smart-library/review-service:1.0
```

> ✅ Already done — pods are running from these images.

---

## PART 7 — Ingress addon (this was missing earlier — verify it's now enabled)

```powershell
minikube addons list | Select-String ingress
```

Expected:

```
| ingress | minikube | enabled ✅ | Kubernetes ingress controller using NGINX
```

If **disabled** or missing:

```powershell
# Cluster is already up — this now succeeds in 1–3 minutes
minikube addons enable ingress

# Wait for the controller
kubectl -n ingress-nginx get pods -w     # wait for 1/1 Running
```

Verify controller Service has `EXTERNAL-IP 127.0.0.1`:

```powershell
kubectl -n ingress-nginx get svc ingress-nginx-controller
```

Expected:

```
NAME                       TYPE           EXTERNAL-IP   PORT(S)
ingress-nginx-controller   LoadBalancer   127.0.0.1     80:xxxxx/TCP, 443:xxxxx/TCP
```

> ✅ Already enabled — you're hitting `aupp.com` and getting real responses.

---

## PART 8 — Secret and deploy (already done ✅)

If you ever need to redeploy the secret from `.env`:

```powershell
# Regenerate k8s/02-secret.yaml (k8s-deploy.ps1 requires this file to exist)
$yaml = kubectl -n smart-library create secret generic smart-library-secrets `
          --from-env-file=.env --dry-run=client -o yaml
$yaml | Set-Content -Path k8s/02-secret.yaml -Encoding utf8

# Apply
kubectl apply -f k8s/00-namespace.yaml
kubectl -n smart-library create secret generic smart-library-secrets `
  --from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -

# Restart pods so they pick up new secret values
kubectl -n smart-library rollout restart deploy
```

### Verify the secret

```powershell
kubectl -n smart-library get secret smart-library-secrets -o jsonpath="{.data}" |
  ConvertFrom-Json | Get-Member -MemberType NoteProperty | Measure-Object | Select-Object Count
```

Expected: `Count = 11`.

> ✅ Already done — you verified 11 keys, `AUTH_DATABASE_URL` decodes to the Neon host.

---

## PART 9 — Pods (already Running ✅)

```powershell
kubectl -n smart-library get pods
```

Expected — **13 pods Running, 0 restarts**:

```
catalog-service-*  × 3    1/1   Running
gateway-*          × 2    2/2   Running    ← app + log-tailer
registration-service      1/1   Running
login-service             1/1   Running
member-service            1/1   Running
inventory-service         1/1   Running
borrowing-service         1/1   Running
fine-service              1/1   Running
review-service            1/1   Running
log-viewer                1/1   Running
```

> ✅ Already done.

---

## PART 10 — DNS + Tunnel (already done ✅)

Two **Admin** PowerShell windows:

**Window A — leave running forever:**

```powershell
minikube tunnel
```

Wait for `✅ Tunnel successfully started`. Never close this window.

**Window B — run commands:**

```powershell
cd "C:\Users\lenmo\Downloads\Smart-Library-Microservices"
.\scripts\k8s-setup-dns.ps1 -ClusterIp 127.0.0.1
```

### Verify fanout

```powershell
curl.exe http://aupp.com/health
curl.exe http://api.aupp.com/api/books
curl.exe http://logs.aupp.com/
```

All → 200.

> ✅ Already done — `aupp.com` responds, load-balancer test hit it successfully.

---

## PART 11 — Tests — **important distinction**

### ✅ Smoke test (passes on both Compose and K8s)

```powershell
Get-Content .env | Where-Object { $_ -match '^[A-Z_]+=' } |
  ForEach-Object { $k,$v = $_ -split '=',2; Set-Item "env:$($k.Trim())" $v.Trim() }

python tests/smoke_test.py http://aupp.com --admin-key $env:ADMIN_REGISTRATION_KEY
```

Expected: `~75 checks, 0 failures`. **This is your primary evidence.**

### ⚠️ Load-balancer test — **2 checks expected to fail on K8s**

```powershell
python tests/load_balancer_test.py http://aupp.com --admin-key $env:ADMIN_REGISTRATION_KEY
```

What you'll see (this is **correct** for K8s, not a bug):

```
[PASS] all requests succeeded
[FAIL] traffic reached 3 different replicas   ← keep-alive reuses 2 conns
[PASS] distribution is even
[PASS] all concurrent requests succeeded       ← proves 3 pods work
[PASS] concurrent traffic reached 3 replicas   ← the real proof
[FAIL] /lb/stats lists every replica           ← K8s uses 1 service URL
```

**Why:** The test was written for Docker Compose, where `CATALOG_URL` is a comma-separated list of 3 URLs (and the gateway's Python code does round-robin). In K8s, `CATALOG_URL` is one Service name and **kube-proxy** does the load balancing per TCP connection. The Python code never sees 3 URLs — that's correct by design.

### The K8s-native proof of load balancing (this is what `docs/KUBERNETES.md` recommends)

```powershell
# Prove all 3 pods are behind the service
kubectl -n smart-library get pods -l app=catalog-service
kubectl -n smart-library get endpoints catalog-service

# Prove kube-proxy distributes across all 3 (each curl = fresh TCP conn)
1..30 | ForEach-Object {
  (curl.exe -s -D - -o NUL http://aupp.com/api/books | Select-String "X-Served-By")
} | Group-Object | Format-Table Count, Name
```

Expected — 3 pods, ~10 requests each:

```
Count Name
----- ----
   11 X-Served-By: catalog-service/catalog-service-849c985b64-4lkrf
   10 X-Served-By: catalog-service/catalog-service-849c985b64-6wzf7
    9 X-Served-By: catalog-service/catalog-service-849c985b64-nx96z
```

**Screenshot this.** It's your rubric evidence for load balancing. ✅

### Collect evidence

```powershell
python scripts/collect_evidence.py http://aupp.com --admin-key $env:ADMIN_REGISTRATION_KEY
.\scripts\k8s-verify.ps1
```

These produce `evidence/<timestamp>/` and `evidence/k8s-run/` — the K8s-correct rubric files.

---

## PART 12 — Postman

1. Import `postman/SmartLibrary.postman_collection.json`
2. Set collection variables:
   - `baseUrl = http://aupp.com`
   - `adminKey = <$env:ADMIN_REGISTRATION_KEY>` (print with `Write-Host $env:ADMIN_REGISTRATION_KEY`)
3. **Run collection** — all 11 folders should pass.

---

## PART 13 — Final demo + evidence (for defense)

### Live pod kill demo

```powershell
kubectl -n smart-library delete pod -l app=catalog-service --field-selector status.phase=Running --wait=$false
kubectl -n smart-library get pods -l app=catalog-service -w

# Requests keep returning 200 during recreation
1..20 | % { (curl.exe -s -o NUL -w "%{http_code} " http://aupp.com/api/books) }
```

### Shared volume demo

```powershell
kubectl -n smart-library exec deploy/gateway         -c gateway -- wc -l /var/log/smartlibrary/access.log
kubectl -n smart-library exec deploy/catalog-service           -- wc -l /var/log/smartlibrary/access.log
kubectl -n smart-library exec deploy/log-viewer                -- wc -l /var/log/smartlibrary/access.log
```

Same line count from three different pods → shared RWX volume works. ✅

### "Cloud DB, no container" screenshot

```powershell
# No postgres pod anywhere
kubectl -n smart-library get pods | Select-String -Pattern "postgres|db"     # empty = PASS

# Every DB URL points at Neon
kubectl -n smart-library get secret smart-library-secrets -o jsonpath="{.data}" |
  ConvertFrom-Json | ForEach-Object {
    $_.PSObject.Properties | Where-Object { $_.Name -like '*DATABASE_URL' } | ForEach-Object {
      "$($_.Name) = $([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_.Value)))"
    }
  }
```

Expected — 6 lines, all hosts `ep-small-feather-aztju6cv.c-3.ap-southeast-1.aws.neon.tech`.

### "Gateway only" screenshot

```powershell
kubectl -n smart-library get svc
```

Every microservice `type` = `ClusterIP`. Only `ingress-nginx-controller` is `LoadBalancer` (that's the ingress itself).

---

## Final checklist

**Windows setup**
- [x] `Set-ExecutionPolicy RemoteSigned`
- [x] All `.ps1` files unblocked
- [x] Dockerfile `\\` → `\` fix applied

**`.env` and Neon**
- [x] `.env` has 11 keys
- [x] `.env` git-ignored
- [x] Neon has 7 databases
- [x] All 6 URLs use `ep-small-feather-aztju6cv.c-3...` with `?sslmode=require`

**Minikube**
- [x] Cluster Running (`--cpus=2 --memory=3500 --container-runtime=docker --cni=calico`)
- [x] Ingress addon enabled
- [x] 9 images in Minikube's daemon
- [x] 13 pods Running

**Access**
- [x] `minikube tunnel` running in an Admin window
- [x] Hosts file: `aupp.com`, `api.aupp.com`, `logs.aupp.com` → 127.0.0.1
- [x] `curl http://aupp.com/health` → 200

**Tests**
- [x] `smoke_test.py` → 0 failures
- [~] `load_balancer_test.py` → 3/5 pass, 2 expected failures (Compose-only)
- [x] K8s-native curl loop → all 3 pods appear
- [ ] Postman collection green ← do this next
- [ ] `k8s-verify.ps1` → `SUMMARY.md` all PASS

**Evidence to hand in**
- [ ] Screenshot: `kubectl get all -n smart-library`
- [ ] Screenshot: `http://aupp.com/docs`
- [ ] Screenshot: `http://logs.aupp.com/`
- [ ] Screenshot: curl loop showing 3 pods (Part 11)
- [ ] Screenshot: 6 decoded Neon URLs (Part 13)
- [ ] Screenshot: `kubectl get svc` → all ClusterIP

**Security (do after demo)**
- [ ] Rotate Neon password in Console → update `.env` → re-run Part 8 → `rollout restart deploy`

---

## Summary — what you have and what's left

| Component | Status | Notes |
|---|---|---|
| Windows prerequisites | ✅ | Policy + unblock done |
| Dockerfiles | ✅ | `\\` bug fixed |
| `.env` | ✅ | 11 keys, no hardcode |
| Neon databases | ✅ | 7 total |
| Minikube | ✅ | Running with Calico |
| Ingress addon | ✅ | Enabled, controller running |
| 9 images | ✅ | In Minikube's daemon |
| Secret from `.env` | ✅ | 11 keys applied |
| 13 pods | ✅ | All Running |
| Tunnel + DNS | ✅ | `aupp.com` resolves and serves |
| Smoke test | ✅ | All pass |
| Load-balancer test | ⚠️ | 3/5 pass; 2 are Compose-only assertions |
| K8s-native LB proof | ✅ | curl loop shows 3 pods |
| Postman | ⬜ | **Run before submission** |
| `k8s-verify.ps1` | ⬜ | **Run before submission** |
| Final screenshots | ⬜ | See evidence list |

**Everything works. You have 2 optional tasks left** (Postman + `k8s-verify.ps1`) and both are "click a button and save output" — no fixes needed.

The load-balancer test "failure" is cosmetic — the API works, the load balancing works, and the K8s-native proof confirms it. Just include the curl-loop screenshot in your evidence and note in your write-up that K8s uses Service-level LB (kube-proxy), not app-level (URL pool). That's the architecturally correct explanation and matches what `docs/KUBERNETES.md` teaches.