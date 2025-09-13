from __future__ import annotations

import asyncio
import httpx
from typing import Optional, Tuple
import inspect
from .config import settings


DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    # Some sites check these
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


async def fetch_with_httpx(
    url: str,
    timeout_seconds: int,
    retries: int,
    proxy: Optional[str],
    user_agent: str,
    max_bytes: int,
    allow_insecure_ssl: Optional[bool] = None,
) -> Tuple[int, str, bytes, Optional[str]]:
    """
    Returns: (status_code, final_url, content_bytes, content_type)
    """
    headers = DEFAULT_HEADERS.copy()
    headers["User-Agent"] = user_agent

    limits = httpx.Limits(max_connections=10, max_keepalive_connections=4)
    timeout = httpx.Timeout(timeout_seconds)

    # Determine SSL verification based on per-request override or global setting
    verify_ssl = not (allow_insecure_ssl if allow_insecure_ssl is not None else settings.allow_insecure_ssl)

    client_kwargs = dict(
        follow_redirects=True,
        headers=headers,
        timeout=timeout,
        limits=limits,
        cookies=httpx.Cookies(),
        http2=True,
        verify=verify_ssl,
    )
    try:
        sig = inspect.signature(httpx.AsyncClient)
        if "proxies" in sig.parameters and proxy:
            client_kwargs["proxies"] = proxy
    except Exception:
        # If inspection fails, just skip proxies for broad compatibility
        pass

    async with httpx.AsyncClient(**client_kwargs) as client:
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                # Stream to enforce max_bytes
                async with client.stream("GET", url) as resp:
                    status = resp.status_code
                    final_url = str(resp.url)
                    ctype = resp.headers.get("content-type")
                    buf = bytearray()
                    async for chunk in resp.aiter_bytes():
                        if chunk:
                            buf.extend(chunk)
                            if len(buf) > max_bytes:
                                # Abort reading
                                break
                    return status, final_url, bytes(buf[:max_bytes]), ctype
            except Exception as e:
                last_exc = e
                # Exponential backoff with cap
                await asyncio.sleep(min(2 ** attempt, 5))
        # If we get here, retries exhausted
        if last_exc:
            raise last_exc
        raise RuntimeError("Unknown fetch error")
