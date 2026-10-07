# AUTO-COPIED from services/_common/core/balancer.py - edit it there and run scripts/sync_common.py
"""Round-robin load balancing with passive health tracking, shared by the gateway and the service clients.

An upstream is given as one URL or a comma-separated list of URLs (one per running replica):
    CATALOG_URL=http://catalog-1:8003,http://catalog-2:8003,http://catalog-3:8003
Requests rotate over the replicas that are believed to be up. A replica that refuses connections is
taken out of rotation for `cooldown` seconds and the request is retried on the next one (failover).
"""
import threading
import time


class UpstreamPool:
    def __init__(self, urls: str | list[str], cooldown: float = 10.0):
        raw = urls.split(",") if isinstance(urls, str) else urls
        self.urls = [u.strip().rstrip("/") for u in raw if u and u.strip()]
        if not self.urls:
            raise ValueError("At least one upstream URL is required.")
        self.cooldown = cooldown
        self._lock = threading.Lock()
        self._turn = 0
        self._down_until = {u: 0.0 for u in self.urls}
        self.requests = {u: 0 for u in self.urls}
        self.failures = {u: 0 for u in self.urls}

    def candidates(self) -> list[str]:
        """URLs in the order they should be tried: next healthy replica (round-robin) first."""
        with self._lock:
            now = time.monotonic()
            healthy = [u for u in self.urls if self._down_until[u] <= now] or list(self.urls)
            first = healthy[self._turn % len(healthy)]
            self._turn += 1
            rest = [u for u in healthy if u != first] + [u for u in self.urls if u not in healthy]
            return [first] + rest

    def record(self, url: str) -> None:
        with self._lock:
            self.requests[url] += 1
            self._down_until[url] = 0.0

    def mark_down(self, url: str) -> None:
        with self._lock:
            self.failures[url] += 1
            self._down_until[url] = time.monotonic() + self.cooldown

    def is_up(self, url: str) -> bool:
        with self._lock:
            return self._down_until[url] <= time.monotonic()

    def snapshot(self) -> list[dict]:
        with self._lock:
            now = time.monotonic()
            return [{"url": u, "status": "up" if self._down_until[u] <= now else "down",
                     "requests": self.requests[u], "failures": self.failures[u]} for u in self.urls]
