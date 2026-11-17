#!/usr/bin/env python3
"""Runs every automated test against a running system and saves the output as evidence (for the report / demo).

    python scripts/collect_evidence.py                                         # local stack on http://127.0.0.1:8000
    python scripts/collect_evidence.py http://<EC2-1 public IP>:8000 --admin-key <ADMIN_REGISTRATION_KEY>

Creates  evidence/<timestamp>/  with  SUMMARY.md, smoke_test.txt, load_balancer_test.txt, health_services.json
and newman.txt (only if Newman, the Postman CLI, is installed: npm install -g newman).
"""
import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("base", nargs="?", default="http://127.0.0.1:8000")
ap.add_argument("--admin-key", default="local-admin-key")
ap.add_argument("--out", default=str(ROOT / "evidence"))
args = ap.parse_args()

stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
out = Path(args.out) / stamp
out.mkdir(parents=True, exist_ok=True)
results: list[tuple[str, bool, str]] = []


def run(name: str, cmd: list[str], file: str, note: str = ""):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    (out / file).write_text(p.stdout + (("\n--- stderr ---\n" + p.stderr) if p.stderr.strip() else ""))
    results.append((name, p.returncode == 0, file))
    print(f"[{'PASS' if p.returncode == 0 else 'FAIL'}] {name}  ->  {out.name}/{file}")


health = httpx.get(f"{args.base}/health/services", timeout=15).json()
(out / "health_services.json").write_text(json.dumps(health, indent=2))
print("services:", health["services"])

py = sys.executable
run("End-to-end API test through the gateway (RBAC, validation, all 9 services)",
    [py, "tests/smoke_test.py", args.base, "--admin-key", args.admin_key], "smoke_test.txt")
run("Load-balancing test (distribution over replicas + gateway counters)",
    [py, "tests/load_balancer_test.py", args.base, "--admin-key", args.admin_key], "load_balancer_test.txt")
newman = shutil.which("newman")
if newman:
    run("Postman collection run (Newman)",
        [newman, "run", "postman/SmartLibrary.postman_collection.json", "--folder", "0 - Gateway health", "--folder", "1 - Registration service",
         "--folder", "2 - Login service (JWT)", "--folder", "3 - Member service (Member 1)", "--folder", "4 - Catalog service (Member 1)",
         "--folder", "5 - Inventory service (Member 2)", "--folder", "6 - Borrowing service (Member 2)", "--folder", "7 - Fine service (Member 3)",
         "--folder", "8 - Review service (Member 3)", "--env-var", f"baseUrl={args.base}", "--env-var", f"adminKey={args.admin_key}",
         "--reporter-cli-no-banner"], "newman.txt")

lines = [f"# Test evidence", "", f"* **Date:** {dt.datetime.now():%Y-%m-%d %H:%M:%S}", f"* **Target:** `{args.base}`",
         f"* **Services:** " + ", ".join(f"{k}: {v}" for k, v in health["services"].items()), "",
         "| Test | Result | Output file |", "|---|---|---|"]
lines += [f"| {n} | {'PASS' if ok else 'FAIL'} | `{f}` |" for n, ok, f in results]
(out / "SUMMARY.md").write_text("\n".join(lines) + "\n")
print(f"\nEvidence saved in {out}")
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
