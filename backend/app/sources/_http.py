"""Shared read-only HTTP helper. Only GET is exposed here on purpose — this is
the enforcement point for the 'read-only on all external sources' invariant."""
from __future__ import annotations

import random
import time
import httpx
from ..config import config

_HEADERS = {"User-Agent": config.USER_AGENT}

# Never block a request thread for more than this on a single retry sleep, even
# if the server's Retry-After asks for longer (e.g. arXiv IP blocks can be minutes
# — waiting that long inline is worse than degrading and letting other sources fill in).
_MAX_RETRY_SLEEP = 30.0


def _retry_sleep(resp: httpx.Response, attempt: int, backoff: float) -> float:
    """How long to wait before the next attempt: the larger of a jittered
    exponential backoff and the server's Retry-After hint, capped at _MAX_RETRY_SLEEP."""
    wait = backoff * (2 ** attempt)
    ra = resp.headers.get("Retry-After")
    if ra:
        try:                       # Retry-After: <seconds> (the HTTP-date form is ignored)
            wait = max(wait, float(int(ra)))
        except ValueError:
            pass
    return min(wait, _MAX_RETRY_SLEEP) + random.uniform(0, backoff * 0.5)


def get(url: str, *, params: dict | None = None, timeout: float = 25.0,
        headers: dict | None = None, follow_redirects: bool = True,
        retries: int = 0, backoff: float = 3.0) -> httpx.Response:
    """Read-only GET. Politely retries on 429/503, honoring the server's
    Retry-After header and otherwise using jittered exponential backoff (free
    scholarly APIs rate-limit aggressively). The per-sleep cap keeps a hard
    rate-limit from stalling the request — the caller degrades gracefully."""
    h = dict(_HEADERS)
    if headers:
        h.update(headers)
    resp = None
    with httpx.Client(timeout=timeout, follow_redirects=follow_redirects, headers=h) as client:
        for attempt in range(retries + 1):
            resp = client.get(url, params=params)
            if resp.status_code not in (429, 503) or attempt == retries:
                return resp
            time.sleep(_retry_sleep(resp, attempt, backoff))
    return resp
