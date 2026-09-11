"""
Phase 6: a small, honest, in-memory rate limiter.

WHAT THIS IS: a per-process, fixed-window counter keyed by client IP,
applied as a FastAPI dependency to the endpoints most worth protecting
from brute-force/abuse (POST /auth/login, POST /auth/register,
POST /upload-analyze). No new dependency was added for this -- it's a
few dozen lines of stdlib code, per Phase 6's instruction not to pull in
a large library "just for theoretical protection".

WHAT THIS IS NOT, HONESTLY (see Phase 6 report's "Remaining Security
Limitations"):
    - It is NOT distributed. State lives in this process's memory only.
      Running multiple uvicorn/gunicorn workers, or multiple instances
      behind a load balancer, means each process enforces its own
      separate limit -- an attacker spread across workers effectively
      gets (limit * worker_count) requests, not `limit`.
    - It resets on every restart/deploy.
    - It trusts `request.client.host`, which is the direct TCP peer.
      Behind a reverse proxy/load balancer that doesn't forward and
      configure the real client IP (e.g. via a trusted X-Forwarded-For),
      every request can appear to come from the proxy's own IP, making
      the limit apply to ALL traffic collectively rather than per real
      client.
    - It is a basic abuse deterrent for this MVP, not a substitute for
      a real gateway-level rate limiter (nginx/Cloudflare/API gateway)
      or a shared store (Redis) in a real multi-instance deployment.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

# Registry of every limiter instance created via rate_limit() below, so
# tests can reset all of them between test cases (see reset_all() and
# tests/conftest.py's autouse fixture). Not used by the running
# application itself.
_ALL_LIMITERS: list["_FixedWindowRateLimiter"] = []


def reset_all() -> None:
    """Reset every rate limiter created so far. Intended for test setup
    only (see tests/conftest.py) -- resets in-memory request counts
    between tests so one test's calls to a rate-limited endpoint can
    never cause an unrelated test to unexpectedly hit 429."""
    for limiter in _ALL_LIMITERS:
        limiter.reset()


class _FixedWindowRateLimiter:
    """Allows at most `max_requests` calls per `window_seconds`, per key
    (here, client IP). Thread-safe (a single lock guards the shared
    dict) since FastAPI can run sync dependencies in a thread pool."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()
        _ALL_LIMITERS.append(self)

    def reset(self) -> None:
        """Clear all recorded hits. Used between tests (see
        tests/conftest.py's autouse fixture) so one test's requests to a
        rate-limited endpoint never carry over and trip the limit in an
        unrelated test -- this has no effect outside tests, since
        nothing in the running application calls it."""
        with self._lock:
            self._hits.clear()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_requests:
                retry_after = max(0, self.window_seconds - (now - hits[0]))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(int(retry_after) + 1)},
                )
            hits.append(now)


def rate_limit(max_requests: int, window_seconds: float):
    """FastAPI dependency factory. Usage:

        @router.post("/login", dependencies=[Depends(rate_limit(5, 60))])

    A fresh limiter instance per call site (per decorated route), so
    the login and register limits are tracked independently of each
    other.
    """
    limiter = _FixedWindowRateLimiter(max_requests, window_seconds)

    def _dependency(request: Request) -> None:
        client_host = request.client.host if request.client else "unknown"
        limiter.check(client_host)

    return _dependency