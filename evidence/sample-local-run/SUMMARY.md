# Test evidence

* **Date:** 2026-10-07 04:27:28
* **Target:** `http://127.0.0.1:8000`
* **Services:** registration: up, login: up, catalog: up (3/3 instances), member: up, inventory: up, borrowing: up, fine: up, review: up

| Test | Result | Output file |
|---|---|---|
| End-to-end API test through the gateway (RBAC, validation, all 9 services) | PASS | `smoke_test.txt` |
| Load-balancing test (distribution over replicas + gateway counters) | PASS | `load_balancer_test.txt` |
| Postman collection run (Newman) | PASS | `newman.txt` |
