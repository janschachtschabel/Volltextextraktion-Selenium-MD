from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urljoin, urlparse
import random
from bs4 import BeautifulSoup


def _soup(html: str, parser: str = "lxml") -> BeautifulSoup:
    try:
        return BeautifulSoup(html, parser)
    except Exception:
        # Fallback to built-in parser if lxml is unavailable
        return BeautifulSoup(html, "html.parser")


ERROR_HINTS = [
    # English
    "404", "not found", "page not found", "access denied", "forbidden", "error",
    "temporarily unavailable", "maintenance", "bad gateway", "gateway timeout",
    "service unavailable", "captcha", "bot detection", "cloudflare",
    # German
    "seite nicht gefunden", "nicht gefunden", "fehler", "zugriff verweigert",
    "vorübergehend nicht verfügbar", "wartung", "nicht erreichbar", "cookie erforderlich",
]


def detect_error_page(text: str, status_code: int | None) -> bool:
    if status_code and status_code >= 400:
        return True
    lower = text.lower()
    for hint in ERROR_HINTS:
        if hint in lower:
            return True
    return False


def extract_links_from_html(html: str, base_url: str) -> list[str]:
    soup = _soup(html)
    links: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href:
            continue
        absolute = urljoin(base_url, href)
        links.append(absolute)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for l in links:
        if l not in seen:
            seen.add(l)
            unique.append(l)
    return unique


# Heuristics for link classification
SOCIAL_DOMAINS = {
    "twitter.com", "x.com", "facebook.com", "instagram.com", "linkedin.com",
    "youtube.com", "t.me", "tiktok.com", "mastodon.social", "github.com",
    "medium.com", "reddit.com",
}

DOWNLOAD_EXTS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".zip", ".rar", ".7z", ".csv", ".txt",
}


def _is_internal(link: str, base_url: str) -> bool:
    try:
        a = urlparse(link)
        b = urlparse(base_url)
        return a.hostname == b.hostname
    except Exception:
        return False


def _classify_link(url: str, text: str | None) -> str:
    u = url.lower()
    # anchors and javascript
    if u.startswith("javascript:"):
        return "anchor"
    if u.startswith("#"):
        return "anchor"

    # social domains
    try:
        host = urlparse(u).hostname or ""
    except Exception:
        host = ""
    if any(host.endswith(d) for d in SOCIAL_DOMAINS):
        return "social"

    # legal
    if re.search(r"/(impressum|datenschutz|privacy|agb|terms|cookies?)($|/)", u):
        return "legal"

    # auth
    if re.search(r"/(login|logout|sign(in|out|up)|register)($|/)", u):
        return "auth"

    # search
    if re.search(r"/(search|suche)($|/)|[?&](q|query|search|suche)=", u):
        return "search"

    # contact
    if re.search(r"/(contact|kontakt|support|help)($|/)", u):
        return "contact"

    # download by extension
    path = urlparse(u).path
    for ext in DOWNLOAD_EXTS:
        if path.endswith(ext):
            return "download"

    # nav heuristics via link text
    if text:
        t = text.strip().lower()
        if t in {"home", "start", "startseite", "nach oben", "top", "menu", "menü"}:
            return "nav"

    return "content"


def extract_links_detailed_from_html(html: str, base_url: str) -> list[dict]:
    """Return list of dicts: {url, text, internal, category}.

    Uses heuristics to classify links and determines internal vs external.
    """
    soup = _soup(html)
    items: list[dict] = []
    for tag in soup.find_all("a", href=True):
        href = (tag.get("href") or "").strip()
        if not href:
            continue
        text = (tag.get_text() or "").strip() or None
        absolute = urljoin(base_url, href)
        category = _classify_link(href, text)
        internal = _is_internal(absolute, base_url)
        items.append({
            "url": absolute,
            "text": text,
            "internal": internal,
            "category": category,
        })
    # Deduplicate by URL+text
    seen = set()
    unique: list[dict] = []
    for it in items:
        key = (it["url"], it.get("text"))
        if key not in seen:
            seen.add(key)
            unique.append(it)
    return unique


MIME_TO_EXT = {
    "text/html": ".html",
    "application/xhtml+xml": ".html",
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "text/plain": ".txt",
    "application/json": ".json",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def guess_extension(content_type: str | None, default: str = ".bin") -> str:
    if not content_type:
        return default
    ctype = content_type.split(";")[0].strip().lower()
    return MIME_TO_EXT.get(ctype, default)


def normalize_proxy(proxy: str | None) -> str | None:
    """Return a valid proxy URL or None.

    - Treat "string" or "" or whitespace as None (OpenAPI default noise)
    - Require a scheme in {http, https, socks5, socks5h, socks4}; otherwise None
    """
    if not proxy:
        return None
    s = proxy.strip()
    if not s or s.lower() == "string":
        return None
    parsed = urlparse(s)
    if parsed.scheme.lower() in {"http", "https", "socks5", "socks5h", "socks4"}:
        return s
    return None


UA_POOL = [
    # Modern desktop Chrome variants
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # A Firefox variant
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
]


def pick_user_agent(default_ua: str | None = None) -> str:
    pool = UA_POOL.copy()
    if default_ua and default_ua not in pool:
        pool.append(default_ua)
    return random.choice(pool)
