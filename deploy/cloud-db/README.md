# Cloud database setup

Guideline 4: *"Implement appropriate database connectivity for your microservices container according
to the functional requirements of your project. Don't use any docker container database — try to use
any cloud database."*

There is **no PostgreSQL container anywhere in `k8s/`** — no Deployment, no StatefulSet, no Service, no
data volume. Each service reaches a managed PostgreSQL instance over TLS using a connection string held
in the `smart-library-secrets` Secret.

## Which provider

Any managed PostgreSQL works. Free tiers that are enough for this project:

| Provider | Free tier | Multiple databases | Notes |
|---|---|---|---|
| **Neon** | 0.5 GB, no card | Yes | Recommended — fastest signup, true `CREATE DATABASE` |
| Aiven | 1 month trial | Yes | Plain PostgreSQL |
| Supabase | 500 MB | No (one db) | Use one schema per service, see the SQL file |
| Amazon RDS | 12-month free tier | Yes | Best if you also deploy the cluster on EC2 |

## Neon — step by step

1. Sign up at `neon.tech` and create a project named `smart-library`. Pick the region closest to you.
2. Open **SQL Editor** and run the statements in `init-cloud-databases.sql`, one `CREATE DATABASE` at a
   time (Neon runs the editor in a transaction, and `CREATE DATABASE` cannot run inside one).
3. Open **Connection Details**, choose **Parameters only**, and note the host, user, and password.
4. Build the six URLs in this shape:

   ```
   postgresql+psycopg2://USER:PASSWORD@HOST/DBNAME?sslmode=require
   ```

   `sslmode=require` is not optional — Neon and Supabase refuse plaintext connections.
5. Generate the Secret:

   ```powershell
   .\scripts\k8s-make-secret.ps1
   ```

   It prompts for the host, user and password, generates the three application secrets, and writes
   `k8s/02-secret.yaml` (git-ignored).

## Amazon RDS — if you deploy on EC2

1. Create a **PostgreSQL 16, db.t3.micro, 20 GB** instance, *Free tier* template.
2. Set **Public access** to *No*, and put it in the same VPC as the EC2 instance running Minikube.
3. In the RDS security group, allow inbound TCP 5432 **only** from the EC2 instance's security group.
4. Connect from the EC2 box and run `init-cloud-databases.sql`.
5. Use `?sslmode=require` with the RDS CA, same URL shape as above.

## Verifying connectivity from inside the cluster

```powershell
kubectl -n smart-library run psql-probe --rm -it --restart=Never `
  --image=postgres:16-alpine `
  --env="PGPASSWORD=<password>" `
  -- psql -h <host> -U <user> -d catalog_db -c "\dt"
```

This is a one-off throwaway Pod used as a `psql` **client**; it is not a database running in the
cluster. The real check is that each service's `/health` endpoint returns `ok` after start-up, which
only happens once SQLAlchemy has created its tables against the cloud instance.

## Why one database per service

Each service owns its data and no service reads another service's tables — cross-service reads go
through HTTP calls to the owning service. `auth_db` is the one shared database, used by Registration,
Login and Member, because all three operate on the same `users` table. See `docs/DATABASE.md` for the
schema.
