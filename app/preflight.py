from __future__ import annotations

import re
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .http_fetcher import DEFAULT_HEADERS


async def preflight(
    url: str,
    timeout_seconds: int,
    user_agent: str,
) -> Dict[str, Any]:
    """Lightweight HTTP probe to choose a crawl strategy.

    Returns a dict with keys:
    - status: int
    - final_url: str
    - content_type: Optional[str]
    - content_bytes: bytes (may be empty if not text-like)
    - html_text: Optional[str]
    - features: dict
    - strategy: str (HTTP_ONLY | JS_LIGHT | JS_LIGHT_CONSENT | HTTP_THEN_JS | PDF | RSS | YOUTUBE | BLOCKED)
    """
    headers = DEFAULT_HEADERS.copy()
    headers["User-Agent"] = user_agent

    async with httpx.AsyncClient(
        follow_redirects=True,
        headers=headers,
        timeout=httpx.Timeout(timeout_seconds),
        http2=True,
    ) as client:
        r = await client.get(url)

    status = r.status_code
    final_url = str(r.url)
    ctype = (r.headers.get("content-type") or "").lower()

    # Quick binary types
    if ctype.startswith("application/pdf") or final_url.lower().endswith(".pdf"):
        return {
            "status": status,
            "final_url": final_url,
            "content_type": r.headers.get("content-type"),
            "content_bytes": r.content,
            "html_text": None,
            "features": {},
            "strategy": "PDF",
        }

    # RSS/Atom
    if "application/rss" in ctype or "application/atom+xml" in ctype:
        return {
            "status": status,
            "final_url": final_url,
            "content_type": r.headers.get("content-type"),
            "content_bytes": r.content,
            "html_text": None,
            "features": {},
            "strategy": "RSS",
        }

    text = r.text or ""
    soup = BeautifulSoup(text, "lxml")

    # Features
    text_len = len(soup.get_text(" ", strip=True))
    has_main = bool(soup.select_one("main, article, #content, #main-content, [role=main], #app, #__next, #root"))
    html_lower = text.lower()
    spa_mark = any(k in html_lower for k in ("__next_data__", "window.__nuxt__", "ng-version", "__apollo_state__"))
    js_required = re.search(r"(enable javascript|activate javascript|ohne javascript)", html_lower, re.I) is not None
    consent = re.search(r"(consent|cookie|datenschutz).*?(accept|zustimmen|einverstanden)", html_lower, re.I) is not None
    bot_wall = re.search(r"(captcha|just a moment|attention required|cloudflare)", html_lower, re.I) is not None
    rss_link = bool(soup.select("link[type='application/rss+xml'], link[type='application/atom+xml']"))

    # YouTube quick path
    you = ("youtube.com/watch" in final_url.lower()) or ("youtu.be/" in final_url.lower())

    # Strategy selection
    if bot_wall:
        strat = "BLOCKED"
    elif you:
        strat = "YOUTUBE"
    elif rss_link:
        strat = "RSS"
    elif text_len >= 800 and (has_main or not spa_mark) and not js_required and not consent:
        strat = "HTTP_ONLY"
    elif spa_mark or (has_main and text_len < 500) or js_required or consent:
        strat = "JS_LIGHT_CONSENT" if consent else "JS_LIGHT"
    else:
        strat = "HTTP_THEN_JS"

    return {
        "status": status,
        "final_url": final_url,
        "content_type": r.headers.get("content-type"),
        "content_bytes": r.content,
        "html_text": text,
        "features": {
            "text_len": text_len,
            "has_main": has_main,
            "spa_mark": spa_mark,
            "js_required": js_required,
            "consent": consent,
            "bot_wall": bot_wall,
            "rss_link": rss_link,
            "youtube": you,
        },
        "strategy": strat,
    }
