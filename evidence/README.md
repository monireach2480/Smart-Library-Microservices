# Evidence

`sample-local-run/` – real output of the automated tests from a run of the complete system on one machine
(9 services, Catalog as 3 replicas, SQLite). It shows what the tests print; **replace it with a run against your EC2
deployment** before the demonstration:

```bash
python scripts/collect_evidence.py http://<EC2-1 public IP>:8000 --admin-key <ADMIN_REGISTRATION_KEY>
```
(creates a new timestamped folder next to this file). See `docs/TESTING.md`.
