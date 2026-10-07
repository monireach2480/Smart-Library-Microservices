#!/usr/bin/env python3
"""End-to-end check that exercises all 9 services THROUGH THE GATEWAY.

    python tests/smoke_test.py                      # http://127.0.0.1:8000
    python tests/smoke_test.py http://<EC2-1 public IP>:8000 --admin-key <ADMIN_REGISTRATION_KEY>
"""
import argparse
import sys
import uuid

import httpx

ap = argparse.ArgumentParser()
ap.add_argument("base", nargs="?", default="http://127.0.0.1:8000")
ap.add_argument("--admin-key", default="local-admin-key")
args = ap.parse_args()

c = httpx.Client(base_url=args.base, timeout=20)
fails = 0


def check(name: str, resp: httpx.Response, expected: int):
    global fails
    ok = resp.status_code == expected
    fails += not ok
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {resp.status_code} (expected {expected})"
          + ("" if ok else f"  -> {resp.text[:200]}"))
    return resp


def auth(token):
    return {"Authorization": f"Bearer {token}"}


run = uuid.uuid4().hex[:8]
PW = "Passw0rd123"
admin_email, member_email = f"admin-{run}@example.com", f"member-{run}@example.com"

print("== Gateway ==")
check("gateway health", c.get("/health"), 200)
r = check("downstream services health", c.get("/health/services"), 200)
print("   ", r.json()["services"])
hr = c.get("/api/books", params={"page_size": 1})
check("gateway adds X-Upstream / X-Served-By / X-Request-ID", httpx.Response(200 if all(k in hr.headers for k in ("x-upstream", "x-served-by", "x-request-id")) else 500), 200)
check("/lb/stats needs a token", c.get("/lb/stats"), 401)
check("internal endpoints blocked", c.post("/api/inventory/internal/checkout", json={"book_id": 1}), 403)

print("== Registration ==")
check("register member", c.post("/api/auth/register", json={"name": "Mia Reader", "email": member_email, "password": PW}), 201)
check("duplicate email -> 409", c.post("/api/auth/register", json={"name": "Mia Reader", "email": member_email, "password": PW}), 409)
check("weak password -> 422", c.post("/api/auth/register", json={"name": "X Y", "email": f"w{run}@example.com", "password": "short"}), 422)
check("admin without key -> 403", c.post("/api/auth/register", json={"name": "Eve", "email": f"e{run}@example.com", "password": PW, "role": "ADMIN"}), 403)
check("register admin with key", c.post("/api/auth/register", headers={"X-Admin-Key": args.admin_key},
      json={"name": "Head Librarian", "email": admin_email, "password": PW, "role": "ADMIN"}), 201)
check("check-email taken", c.get("/api/auth/check-email", params={"email": member_email}), 200)

print("== Login (JWT) ==")
check("wrong password -> 401", c.post("/api/auth/login", json={"email": member_email, "password": "nope12345"}), 401)
admin_tok = check("admin login", c.post("/api/auth/login", json={"email": admin_email, "password": PW}), 200).json()["access_token"]
member = check("member login", c.post("/api/auth/login", json={"email": member_email, "password": PW}), 200).json()
member_tok, member_id = member["access_token"], member["user"]["id"]
check("/me", c.get("/api/auth/me", headers=auth(member_tok)), 200)
check("/verify", c.get("/api/auth/verify", headers=auth(admin_tok)), 200)
check("no token -> 401", c.get("/api/auth/me"), 401)
check("garbage token -> 401", c.get("/api/auth/me", headers=auth("abc.def.ghi")), 401)

print("== Role-based access ==")
check("member cannot list members (gateway) -> 403", c.get("/api/members", headers=auth(member_tok)), 403)
check("member cannot add book -> 403", c.post("/api/books", headers=auth(member_tok), json={}), 403)

print("== Member service ==")
check("admin lists members", c.get("/api/members", headers=auth(admin_tok), params={"q": run}), 200)
check("admin stats", c.get("/api/members/stats", headers=auth(admin_tok)), 200)
check("member sees self", c.get(f"/api/members/{member_id}", headers=auth(member_tok)), 200)
check("member cannot see others -> 403", c.get(f"/api/members/{member_id + 999}", headers=auth(member_tok)), 403)
check("member renames self", c.put(f"/api/members/{member_id}", headers=auth(member_tok), json={"name": "Mia R. Reader"}), 200)

print("== Catalog service ==")
isbn = "9780132350884"  # Clean Code
r = c.post("/api/books", headers=auth(admin_tok), json={
    "title": f"Clean Code {run}", "author": "Robert C. Martin", "isbn": isbn, "category": "Software", "published_year": 2008})
# 409 only means a previous run / the Postman collection already created this ISBN: the system is re-runnable
check("admin adds book (or ISBN already exists from an earlier run)", r, 201 if r.status_code != 409 else 409)
if r.status_code == 409:
    r = c.get("/api/books", params={"q": isbn})
    book_id = r.json()["items"][0]["id"]
else:
    book_id = r.json()["id"]
check("bad ISBN -> 422", c.post("/api/books", headers=auth(admin_tok), json={
    "title": "Bad", "author": "A", "isbn": "1234567890123", "category": "X"}), 422)
check("public search", c.get("/api/books", params={"q": "clean"}), 200)
check("public get book", c.get(f"/api/books/{book_id}"), 200)
check("categories", c.get("/api/categories"), 200)
check("admin updates book", c.put(f"/api/books/{book_id}", headers=auth(admin_tok), json={
    "title": f"Clean Code {run}", "author": "Robert C. Martin", "isbn": isbn, "category": "Software", "published_year": 2009}), 200)

r2 = c.post("/api/books", headers=auth(admin_tok), json={"title": f"Design Patterns {run}", "author": "Gamma et al.",
            "isbn": "9780201633610", "category": "software"})
check("second book reuses the 'Software' category (case-insensitive FK)", r2, 201 if r2.status_code != 409 else 409)
if r2.status_code == 201:
    cats = {x["name"].lower(): x["book_count"] for x in c.get("/api/categories").json()}
    check("category not duplicated", httpx.Response(200 if cats.get("software", 0) >= 2 else 500), 200)
    c.delete(f"/api/books/{r2.json()['id']}", headers=auth(admin_tok))

print("== Inventory service ==")
check("copy for missing book -> 404", c.post("/api/inventory/copies", headers=auth(admin_tok), json={"book_id": 999999, "barcode": f"X-{run}"}), 404)
copy = check("admin adds copy", c.post("/api/inventory/copies", headers=auth(admin_tok), json={"book_id": book_id, "barcode": f"BC-{run}", "shelf_location": "A1"}), 201).json()
check("member cannot add copy -> 403", c.post("/api/inventory/copies", headers=auth(member_tok), json={"book_id": book_id, "barcode": "zzz"}), 403)
check("admin lists copies", c.get("/api/inventory/copies", headers=auth(admin_tok), params={"book_id": book_id}), 200)
check("admin gets one copy", c.get(f"/api/inventory/copies/{copy['id']}", headers=auth(admin_tok)), 200)
spare = check("admin adds a spare copy", c.post("/api/inventory/copies", headers=auth(admin_tok), json={"book_id": book_id, "barcode": f"SP-{run}"}), 201).json()
check("admin deletes the spare copy", c.delete(f"/api/inventory/copies/{spare['id']}", headers=auth(admin_tok)), 204)
check("public availability", c.get(f"/api/inventory/availability/{book_id}"), 200)

print("== Borrowing service (calls Member + Inventory) ==")
loan = check("member borrows", c.post("/api/loans", headers=auth(member_tok), json={"book_id": book_id}), 201).json()
check("borrow same book again -> 409", c.post("/api/loans", headers=auth(member_tok), json={"book_id": book_id}), 409)
check("admin cannot borrow -> 403", c.post("/api/loans", headers=auth(admin_tok), json={"book_id": book_id}), 403)
av = c.get(f"/api/inventory/availability/{book_id}").json()
print(f"    availability now: {av}")
check("cannot delete a copy that is on loan -> 409", c.delete(f"/api/inventory/copies/{loan['copy_id']}", headers=auth(admin_tok)), 409)
check("my loans", c.get("/api/loans/my", headers=auth(member_tok)), 200)
check("admin lists loans", c.get("/api/loans", headers=auth(admin_tok), params={"status": "ACTIVE"}), 200)
check("member lists all loans -> 403", c.get("/api/loans", headers=auth(member_tok)), 403)
check("get loan", c.get(f"/api/loans/{loan['id']}", headers=auth(member_tok)), 200)
ret = check("member returns on time", c.post(f"/api/loans/{loan['id']}/return", headers=auth(member_tok)), 200).json()
check("return twice -> 409", c.post(f"/api/loans/{loan['id']}/return", headers=auth(member_tok)), 409)

print("== Fine service ==")
check("admin creates manual fine", c.post("/api/fines", headers=auth(admin_tok), json={"user_id": member_id, "amount": 3.5, "reason": "Water damaged cover"}), 201)
check("member cannot create fine -> 403", c.post("/api/fines", headers=auth(member_tok), json={"user_id": member_id, "amount": 1, "reason": "self"}), 403)
fines = check("my fines", c.get("/api/fines/my", headers=auth(member_tok)), 200).json()
check("my fine summary", c.get("/api/fines/my/summary", headers=auth(member_tok)), 200)
check("admin lists fines", c.get("/api/fines", headers=auth(admin_tok)), 200)
fid = fines["items"][0]["id"]
paid = check("member pays fine", c.post(f"/api/fines/{fid}/pay", headers=auth(member_tok)), 200).json()
check("payment receipt created (Fine 1:N Payment)", httpx.Response(200 if len(paid.get("payments", [])) == 1 else 500), 200)
check("get fine with receipts", c.get(f"/api/fines/{fid}", headers=auth(member_tok)), 200)
check("paid fine cannot be deleted -> 409", c.delete(f"/api/fines/{fid}", headers=auth(admin_tok)), 409)
extra = c.post("/api/fines", headers=auth(admin_tok), json={"user_id": member_id, "amount": 1.0, "reason": "Waive me please"}).json()
check("member cannot waive a fine -> 403", c.delete(f"/api/fines/{extra['id']}", headers=auth(member_tok)), 403)
check("admin waives an unpaid fine", c.delete(f"/api/fines/{extra['id']}", headers=auth(admin_tok)), 204)
check("pay twice -> 409", c.post(f"/api/fines/{fid}/pay", headers=auth(member_tok)), 409)

print("== Review service ==")
check("review missing book -> 404", c.post("/api/reviews", headers=auth(member_tok), json={"book_id": 999999, "rating": 5}), 404)
rv = check("member reviews book", c.post("/api/reviews", headers=auth(member_tok), json={"book_id": book_id, "rating": 5, "comment": "Great!"}), 201).json()
check("review twice -> 409", c.post("/api/reviews", headers=auth(member_tok), json={"book_id": book_id, "rating": 4}), 409)
check("admin cannot review -> 403", c.post("/api/reviews", headers=auth(admin_tok), json={"book_id": book_id, "rating": 4}), 403)
check("public list reviews", c.get("/api/reviews", params={"book_id": book_id}), 200)
r = check("public rating summary", c.get(f"/api/reviews/summary/{book_id}"), 200)
print("   ", r.json())
check("member edits review", c.put(f"/api/reviews/{rv['id']}", headers=auth(member_tok), json={"rating": 4, "comment": "Still great"}), 200)
check("admin deletes review", c.delete(f"/api/reviews/{rv['id']}", headers=auth(admin_tok)), 204)

print("== Admin account control ==")
check("admin suspends member", c.patch(f"/api/members/{member_id}/status", headers=auth(admin_tok), json={"status": "SUSPENDED"}), 200)
check("suspended member cannot login -> 403", c.post("/api/auth/login", json={"email": member_email, "password": PW}), 403)
check("suspended member cannot borrow -> 403", c.post("/api/loans", headers=auth(member_tok), json={"book_id": book_id}), 403)
check("admin reactivates member", c.patch(f"/api/members/{member_id}/status", headers=auth(admin_tok), json={"status": "ACTIVE"}), 200)
check("change password", c.post("/api/auth/change-password", headers=auth(member_tok), json={"current_password": PW, "new_password": "NewPassw0rd9"}), 204)
check("admin deletes book", c.delete(f"/api/books/{book_id}", headers=auth(admin_tok)), 204)

print(f"\n{'ALL CHECKS PASSED' if not fails else str(fails) + ' CHECK(S) FAILED'}")
sys.exit(1 if fails else 0)
