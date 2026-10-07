# Member 2

**You own:** `registration-service` (common) · `inventory-service` · `borrowing-service` · `deploy/ec2-3-member2/`
**EC2:** #3 (inventory + borrowing); your registration service runs on #1 with the gateway

| Service | Port | DB | Endpoints |
|---|---|---|---|
| registration-service | 8001 | auth_db | `POST /register`, `GET /check-email` |
| inventory-service | 8005 | inventory_db | `POST/GET /inventory/copies`, `GET/DELETE /inventory/copies/{id}`, `PATCH /inventory/copies/{id}/status`, `GET /inventory/availability/{book_id}` (+ internal checkout/return) |
| borrowing-service | 8006 | borrowing_db | `POST /loans`, `GET /loans`, `GET /loans/my`, `GET /loans/{id}`, `POST /loans/{id}/return` |

Your services call: Catalog (Member 1), Member (Member 1), Fine (Member 3).

## Push to GitHub (after Member 1 has pushed the base repo)
```bash
git clone https://github.com/<member1>/smart-library.git
cd smart-library
git checkout -b member2/registration-inventory-borrowing
```
Unzip `smart-library-member2.zip` and **copy the contents of its `smart-library/` folder into the cloned repo** (choose "merge folders" if asked – you only add new files, nothing is overwritten). Then:
```bash
git add .
git commit -m "Add registration, inventory and borrowing services"
git push -u origin member2/registration-inventory-borrowing
```
Open a **Pull Request** on GitHub into `main`.

## Run the full system after merging
```bash
git checkout main && git pull
pip install -r requirements-dev.txt
python scripts/run_local.py        # then: python tests/smoke_test.py
```
