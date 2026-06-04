"""Shared read-only HTTP helper. Only GET is exposed here on purpose — this is
the enforcement point for the 'read-only on all external sources' invariant."""
from __future__ import annotations

import time
import httpx
from ..config import config

_HEADERS = {"User-Agent": config.USER_AGENT}


def get(url: str, *, params: dict | None = None, timeout: float = 25.0,
        headers: dict | None = None, follow_redirects: bool = True,
        retries: int = 0, backoff: float = 3.0) -> httpx.Response:
    """Read-only GET. Politely retries on 429/503 with linear backoff (free
    scholarly APIs rate-limit aggressively)."""
    h = dict(_HEADERS)
    if headers:
        h.update(headers)
    resp = None
    with httpx.Client(timeout=timeout, follow_redirects=follow_redirects, headers=h) as client:
        for attempt in range(retries + 1):
            resp = client.get(url, params=params)
            if resp.status_code not in (429, 503) or attempt == retries:
                return resp
            time.sleep(backoff * (attempt + 1))
    return resp
