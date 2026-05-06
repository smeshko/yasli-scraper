"""Async HTTP fetch with retries and Content-Length verification.

The single ``fetch`` coroutine wraps ``httpx.AsyncClient`` with the retry
policy required by the s03 contract: 3 attempts, exponential backoff
(1s, 2s, 4s), and a Content-Length check on every successful response.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

USER_AGENT = "Mozilla/5.0 (compatible; yasli-scraper/0.2)"


class FetchError(RuntimeError):
    """Raised when all retry attempts have been exhausted."""


class ContentLengthMismatch(RuntimeError):
    """Raised when Content-Length is present but does not match body length."""


async def fetch(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    json: Any = None,
    attempts: int = 3,
    base_backoff: float = 1.0,
) -> bytes:
    """Issue an HTTP request with retries; return raw body bytes.

    Retries on network errors, non-2xx responses, and Content-Length
    mismatches. Backoff is exponential: ``base_backoff * 2**attempt`` (so
    1s, 2s, 4s with the default). The final exception is wrapped in
    ``FetchError`` with the originating cause attached.
    """
    last_err: Exception | None = None
    for attempt in range(attempts):
        if attempt > 0:
            await asyncio.sleep(base_backoff * (2 ** (attempt - 1)))
        try:
            response = await client.request(
                method,
                url,
                json=json,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            body = response.content
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) != len(body):
                raise ContentLengthMismatch(
                    f"Content-Length mismatch for {url}: "
                    f"header={declared} body={len(body)}"
                )
            return body
        except (httpx.HTTPError, ContentLengthMismatch) as exc:
            last_err = exc
    raise FetchError(f"all {attempts} attempts failed for {url}: {last_err}") from last_err
