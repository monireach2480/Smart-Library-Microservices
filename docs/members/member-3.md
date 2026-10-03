# Member 3

**You own:** `login-service` (common) · `fine-service` · `review-service` · `deploy/ec2-4-member3/`
**EC2:** #4 (fine + review); your login service runs on #1 with the gateway

| Service | Port | DB | Endpoints |
|---|---|---|---|
| login-service | 8002 | auth_db | `POST /login`, `GET /me`, `GET /verify`, `POST /change-password` |
| fine-service | 8007 | fine_db | `GET /fines`, `POST /fines`, `GET /fines/my`, `GET /fines/my/summary`, `POST /fines/{id}/pay` (+ internal assess) |
| review-service | 8008 | review_db | `POST/GET /reviews`, `GET /reviews/summary/{book_id}`, `PUT/DELETE /reviews/{id}` |

Your services call: Catalog (Member 1). Borrowing (Member 2) calls your Fine service.

## Push to GitHub (after Member 1 has pushed the base repo)
```bash
git clone https://github.com/<member1>/smart-library.git
cd smart-library
git checkout -b member3/login-fine-review
```
Unzip `smart-library-member3.zip` and **copy the contents of its `smart-library/` folder into the cloned repo** (choose "merge folders" if asked – you only add new files, nothing is overwritten). Then:
```bash
git add .
git commit -m "Add login, fine and review services"
git push -u origin member3/login-fine-review
```
Open a **Pull Request** on GitHub into `main`.

## Run the full system after merging
```bash
git checkout main && git pull
pip install -r requirements-dev.txt
python scripts/run_local.py        # then: python tests/smoke_test.py
```
