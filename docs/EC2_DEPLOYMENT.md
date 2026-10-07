# Deploying on 4 EC2 instances

| Instance | Folder | Runs | Size (suggested) |
|---|---|---|---|
| **EC2 #1** | `deploy/ec2-1-gateway-auth` | Gateway, Registration, Login, **PostgreSQL** | t3.small |
| **EC2 #2** | `deploy/ec2-2-member1` | Catalog (**3 replicas**), Member | t3.small |
| **EC2 #3** | `deploy/ec2-3-member2` | Inventory, Borrowing | t3.micro |
| **EC2 #4** | `deploy/ec2-4-member3` | Fine, Review | t3.micro |

(Using 4 instances stays inside the "maximum 3/4" rule. If you are limited to 3, run EC2 #4's two services on EC2 #3 by merging the two compose files.)

## 1. Create the instances
* AMI: **Ubuntu 24.04**, all four in the **same VPC / region**. Create/choose a key pair.
* Create one security group `library-sg` and attach it to all four instances:

| Port | Source | Why |
|---|---|---|
| 22 | your IP | SSH |
| 8000 | `0.0.0.0/0` | API Gateway (EC2 #1 only matters) |
| 5432, 8001–8008, 8013, 8023 | `library-sg` itself | instances talk to each other privately (8013 and 8023 are the 2nd and 3rd Catalog replica) |
| 8001–8008, 8013, 8023 | *your IP* (optional, temporary) | to demo a single service or replica directly in Postman |

* Note the **private IPv4** of every instance (EC2 console → instance → *Private IPv4 address*) and the **public IP** of EC2 #1.

## 2. Install Docker on each instance
```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER && newgrp docker
git clone <your-repo-url> smart-library && cd smart-library
```

## 3. Generate the secrets once (keep them for all four .env files)
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # SECRET_KEY            (identical on all 4)
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # INTERNAL_API_KEY      (identical on #2, #3, #4)
python3 -c "import secrets; print(secrets.token_urlsafe(16))"   # ADMIN_REGISTRATION_KEY (EC2 #1)
```
Use letters/digits only for `POSTGRES_PASSWORD` (it is embedded in a URL).

## 4. Start in this order
**EC2 #1** (creates the databases):
```bash
cd deploy/ec2-1-gateway-auth && cp .env.example .env && nano .env      # fill in, incl. the 3 other private IPs
docker compose up -d --build
```
**EC2 #2, #3, #4** (after #1 is up – `DB_HOST` = EC2 #1's private IP):
```bash
cd deploy/ec2-2-member1 && cp .env.example .env && nano .env && docker compose up -d --build     # on #2
cd deploy/ec2-3-member2 && cp .env.example .env && nano .env && docker compose up -d --build     # on #3
cd deploy/ec2-4-member3 && cp .env.example .env && nano .env && docker compose up -d --build     # on #4
```
Tables are created automatically on first start.

## 5. Verify
```bash
curl http://<EC2-1 public IP>:8000/health/services      # all 8 should say "up"
python tests/smoke_test.py http://<EC2-1 public IP>:8000 --admin-key <ADMIN_REGISTRATION_KEY>
```
Then import the Postman collection and set `baseUrl = http://<EC2-1 public IP>:8000`.

## 6. Verify load balancing
```bash
python tests/load_balancer_test.py http://<EC2-1 public IP>:8000 --admin-key <ADMIN_REGISTRATION_KEY>
```
Expected: the 3 Catalog replicas on EC2 #2 each serve ~1/3 of the requests. Failover demo: on EC2 #2 run `docker compose stop catalog-service-2`, repeat the test with `--expect 2`, then `docker compose start catalog-service-2`. Details: [LOAD_BALANCING.md](LOAD_BALANCING.md).

## 7. Save evidence
```bash
python scripts/collect_evidence.py http://<EC2-1 public IP>:8000 --admin-key <ADMIN_REGISTRATION_KEY>
```

## Troubleshooting
* `"<name> service is unavailable"` from the gateway → wrong private IP in EC2 #1's `.env`, or the security group does not allow the port from `library-sg`. Fix the `.env`, then `docker compose up -d` again.
* A service restarts in a loop with a connection error → PostgreSQL on EC2 #1 is not reachable: check `DB_HOST`, port 5432 in the security group, and the password.
* Replica not receiving traffic → `/health/services` on the gateway shows which instance is `down`; check port 8013 / 8023 in the security group.
* `401 Invalid token` on one service only → `SECRET_KEY` differs on that instance.
* `403 Internal endpoint` between services → `INTERNAL_API_KEY` differs.
* Logs: `docker compose logs -f <service-name>`.
* Stop everything to save credits: `docker compose down` on each instance (data stays in the `pgdata` volume on EC2 #1).
