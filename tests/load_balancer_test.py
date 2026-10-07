#!/usr/bin/env python3
"""Proves that the gateway load-balances across the replicas of a service.

Sends many requests for the public catalogue through the gateway and counts which replica answered each one
(every service replies with an `X-Served-By: <service>/<instance>` header).

    python tests/load_balancer_test.py                                   # local: http://127.0.0.1:8000
    python tests/load_balancer_test.py http://<EC2-1 public IP>:8000 --admin-key <ADMIN_REGISTRATION_KEY>
    python tests/load_balancer_test.py ... --requests 90 --expect 3

Optional failover check: stop one replica while the test runs (docker stop <container>) and run it again with
--expect 2 -> every request must still succeed and only the 2 remaining replicas serve traffic.
"""
import argparse
import sys
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import httpx

ap = argparse.ArgumentParser()
ap.add_argument("base", nargs="?", default="http://127.0.0.1:8000")
ap.add_argument("--admin-key", default="local-admin-key")
ap.add_argument("--requests", type=int, default=60)
ap.add_argument("--expect", type=int, default=3, help="number of replicas that should be serving traffic")
args = ap.parse_args()

c = httpx.Client(base_url=args.base, timeout=20)
ok = True


def verdict(label, passed, detail=""):
    global ok
    ok &= passed
    print(f"[{'PASS' if passed else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))


print(f"Gateway: {args.base}   requests: {args.requests}   expected replicas: {args.expect}\n")

# --- 1. sequential requests -> round-robin should spread them (almost) perfectly evenly
seq = Counter(); statuses = Counter()
for _ in range(args.requests):
    r = c.get("/api/books", params={"page_size": 1})
    statuses[r.status_code] += 1
    seq[r.headers.get("x-served-by", "?")] += 1
print("1) Sequential requests - answered by:")
for who, n in sorted(seq.items()):
    print(f"   {who:<32} {n:>4}  {'#' * (n * 40 // max(1, args.requests))}")
verdict("all requests succeeded", set(statuses) == {200}, f"status codes: {dict(statuses)}")
verdict(f"traffic reached {args.expect} different replicas", len(seq) == args.expect, f"seen: {len(seq)}")
tolerance = max(1, round(0.1 * args.requests / args.expect))      # a re-probed dead replica can shift a few requests
fair = (max(seq.values()) - min(seq.values()) <= tolerance) if seq else False
verdict(f"distribution is even (difference between replicas <= {tolerance} requests)", fair)

# --- 2. concurrent requests -> still spread over every replica
def hit(_):
    r = c.get("/api/books", params={"page_size": 1})
    return r.status_code, r.headers.get("x-served-by", "?")

with ThreadPoolExecutor(max_workers=12) as pool:
    results = list(pool.map(hit, range(args.requests)))
par = Counter(who for _, who in results)
print("\n2) 12 concurrent clients - answered by:")
for who, n in sorted(par.items()):
    print(f"   {who:<32} {n:>4}")
verdict("all concurrent requests succeeded", all(code == 200 for code, _ in results))
verdict(f"concurrent traffic reached {args.expect} replicas", len(par) == args.expect)

# --- 3. gateway's own counters (ADMIN only)
run = uuid.uuid4().hex[:6]
email = f"lb-admin-{run}@example.com"
c.post("/api/auth/register", headers={"X-Admin-Key": args.admin_key},
       json={"name": "LB Admin", "email": email, "password": "Passw0rd123", "role": "ADMIN"})
login = c.post("/api/auth/login", json={"email": email, "password": "Passw0rd123"})
if login.status_code == 200:
    stats = c.get("/lb/stats", headers={"Authorization": f"Bearer {login.json()['access_token']}"}).json()
    print("\n3) Gateway counters for the catalog service (/lb/stats):")
    for inst in stats["catalog"]:
        print(f"   {inst['url']:<30} status={inst['status']:<5} requests={inst['requests']:<4} failures={inst['failures']}")
    verdict("/lb/stats lists every replica", len(stats["catalog"]) >= args.expect)
else:
    verdict("could not log in as admin for /lb/stats (check --admin-key)", False, login.text[:120])

print("\n" + ("LOAD BALANCING VERIFIED" if ok else "LOAD BALANCING CHECK FAILED"))
sys.exit(0 if ok else 1)
