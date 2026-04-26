"""HTTP client with UA rotation, polite delays, and retry-with-backoff.

Why not just `httpx.get()`?
- Real targets (GitHub Trending HTML, news sites) rate-limit aggressively if you
  hit them with a default UA and no delay between requests.
- A per-host token bucket plus retry-on-5xx-and-network-error is the minimum
  bar for anything that runs unattended (cron, scheduled job).
- Rotating UAs (modern Chrome / Safari / Firefox) reduces signal that something
  scripted is scraping you.

This client is deliberately small. It does not do JS rendering, captcha solving,
or proxy rotation. Those belong in dedicated modules behind the same interface
when a target needs them.
"""
from __future__ import annotations

import asyncio
import logging
import random
from collections import defaultdict
from urllib.parse import urlparse

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

UAS = [
    # Modern Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36",
    # Modern Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.5 Safari/605.1.15",
]


class PoliteClient:
    """Async HTTP client with per-host pacing and retries.

    Usage:
        async with PoliteClient(per_host_delay=1.0) as c:
            r = await c.get("https://example.com/")
            r.raise_for_status()
    """

    def __init__(
        self,
        per_host_delay: float = 1.0,
        timeout: float = 20.0,
        max_attempts: int = 4,
    ) -> None:
        self.per_host_delay = per_host_delay
        self.timeout = timeout
        self.max_attempts = max_attempts
        # last-request time per host to enforce per_host_delay
        self._last: dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "PoliteClient":
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def _wait_turn(self, host: str) -> None:
        async with self._lock:
            loop = asyncio.get_event_loop()
            now = loop.time()
            elapsed = now - self._last[host]
            if elapsed < self.per_host_delay:
                await asyncio.sleep(self.per_host_delay - elapsed)
            self._last[host] = asyncio.get_event_loop().time()

    async def get(self, url: str, **kwargs: object) -> httpx.Response:
        if self._client is None:
            raise RuntimeError("PoliteClient must be used as an async context manager")

        host = urlparse(url).netloc
        await self._wait_turn(host)

        # Rotate UA per request, not per session, so a stable scrape over many
        # requests does not look like one client hammering a target.
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.setdefault("User-Agent", random.choice(UAS))

        async def _do() -> httpx.Response:
            assert self._client is not None
            r = await self._client.get(url, headers=headers, **kwargs)
            # Retry on server errors and rate limit responses
            if r.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError(
                    f"retryable status {r.status_code}", request=r.request, response=r
                )
            return r

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.max_attempts),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                retry=retry_if_exception_type(
                    (httpx.HTTPStatusError, httpx.TransportError)
                ),
                reraise=True,
            ):
                with attempt:
                    return await _do()
        except RetryError as e:
            raise e.last_attempt.exception() from None

        # The retry loop always returns or raises; this line is unreachable.
        raise RuntimeError("unreachable")
