from __future__ import annotations

import time
import asyncio
import logging
import httpx
from selenium.common.exceptions import WebDriverException
from fastapi import FastAPI, HTTPException, Body
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from .config import settings
from .schemas import CrawlRequest, CrawlResponse, LLMResult, LinkInfo
from .http_fetcher import fetch_with_httpx
from .preflight import preflight as preflight_analyze
from .js_fetcher import fetch_with_playwright, cleanup_drivers, get_pool_stats
from .converter import bytes_to_markdown
from .utils import detect_error_page, extract_links_detailed_from_html, normalize_proxy, pick_user_agent
from .llm import postprocess_markdown, postprocess_markdown_async

logger = logging.getLogger(__name__)

# Enhanced request capacity management (simplified and deadlock-safe)
_concurrent_requests = 0
_waiting_count = 0  # number of requests waiting to acquire capacity
_max_concurrent = settings.selenium_max_pool_size  # Use max pool size for better capacity
_request_semaphore = asyncio.Semaphore(_max_concurrent)
_request_lock = asyncio.Lock()


class SmartCapacityMiddleware(BaseHTTPMiddleware):
    """Capacity management using a semaphore and bounded waiting with timeout.

    This design avoids awaiting while holding the internal lock to prevent deadlocks.
    """

    async def dispatch(self, request: Request, call_next):
        global _concurrent_requests, _waiting_count

        # Only apply limits to crawl endpoints
        if request.url.path != "/crawl":
            return await call_next(request)

        # Check if we can enter immediately or must wait. We never await while holding the lock.
        # Enforce a bounded waiting room using _waiting_count against max_queue_size.
        async with _request_lock:
            can_enter_now = _concurrent_requests < _max_concurrent
            if not can_enter_now:
                if _waiting_count >= settings.max_queue_size:
                    logger.warning(
                        f"Request rejected: waiting room full ({_waiting_count}/{settings.max_queue_size})"
                    )
                    return JSONResponse(
                        content={"detail": "Server overloaded. Queue is full. Please retry later."},
                        status_code=503,
                    )
                _waiting_count += 1

        acquired = False
        try:
            # Try to acquire capacity with a timeout (queueing behavior)
            try:
                await asyncio.wait_for(_request_semaphore.acquire(), timeout=settings.queue_timeout_seconds)
                acquired = True
            except asyncio.TimeoutError:
                return JSONResponse(
                    content={"detail": "Request timed out in queue"}, status_code=504
                )

            # We have capacity, update counters
            async with _request_lock:
                if _waiting_count > 0:
                    _waiting_count -= 1
                _concurrent_requests += 1

            # Process the request
            try:
                response = await call_next(request)
                return response
            except Exception as e:
                logger.error(f"Request processing error: {e}")
                return JSONResponse(
                    content={"detail": f"Request processing failed: {str(e)}"}, status_code=502
                )
            finally:
                async with _request_lock:
                    _concurrent_requests -= 1
        finally:
            if acquired:
                _request_semaphore.release()


# Removed request object queuing helpers; semaphore-based waiting is used instead.


app = FastAPI(title="Volltextextraktion Selenium MD", version="0.1.0")
app.add_middleware(SmartCapacityMiddleware)


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up Selenium drivers on shutdown."""
    cleanup_drivers()


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/stats")
async def get_stats():
    """Get current API and pool statistics."""
    pool_stats = get_pool_stats()
    global _concurrent_requests
    
    async with _request_lock:
        queue_size = _waiting_count
        concurrent = _concurrent_requests
    
    return {
        "concurrent_requests": concurrent,
        "max_concurrent": _max_concurrent,
        "queue_size": queue_size,
        "max_queue_size": settings.max_queue_size,
        "selenium_pools": pool_stats,
        "capacity_utilization": {
            "processing": f"{concurrent}/{_max_concurrent}",
            "queue": f"{queue_size}/{settings.max_queue_size}",
            "total_capacity": f"{concurrent + queue_size}/{_max_concurrent + settings.max_queue_size}"
        }
    }


@app.post(
    "/crawl",
    response_model=CrawlResponse,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
                        "url": "https://example.com",
                        "mode": "auto",
                        "js_strategy": "speed",
                        "html_converter": "trafilatura",
                        "trafilatura_clean_markdown": True,
                        "media_conversion_policy": "skip",
                        "allow_insecure_ssl": True,
                        "extract_links": False,
                        "llm_postprocess": False,
                        "llm_anonymize": False,
                        "llm_clean_prompt": None,
                        "retries": 2,
                        "timeout_ms": 30000,
                        "max_bytes": 1048576,
                    }
                }
            }
        }
    },
)
async def crawl(
    req: CrawlRequest = Body(
        ..., 
        example={
            "url": "https://example.com",
            "mode": "auto",
            "js_strategy": "speed",
            "html_converter": "trafilatura",
            "trafilatura_clean_markdown": True,
            "media_conversion_policy": "skip",
            "allow_insecure_ssl": True,
            "extract_links": False,
            "llm_postprocess": False,
            "llm_anonymize": False,
            "llm_clean_prompt": None,
            "retries": 2,
            "timeout_ms": 30000,
            "max_bytes": 1048576,
        },
        openapi_examples={
            "standard": {
                "summary": "Standardvorgaben",
                "description": "Beispiel-Body in gewünschter Reihenfolge",
                "value": {
                    "url": "https://example.com",
                    "mode": "auto",
                    "js_strategy": "speed",
                    "html_converter": "trafilatura",
                    "trafilatura_clean_markdown": True,
                    "media_conversion_policy": "skip",
                    "allow_insecure_ssl": True,
                    "extract_links": False,
                    "llm_postprocess": False,
                    "llm_anonymize": False,
                    "llm_clean_prompt": None,
                    "retries": 2,
                    "timeout_ms": 30000,
                    "max_bytes": 1048576,
                },
            }
        }
    )
):
    """
    Crawlt eine Webseite und konvertiert sie automatisch zu strukturiertem Markdown.
    
    ## 🚀 Drei Modi:
    
    ### `auto` - Automatische Auswahl
    - **Funktionsweise**: Leichte Preflight-Analyse (httpx + HTML-Parsing)
    - **Entscheidung**:
      - PDF/RSS/YouTube → direkte Auslieferung ohne Selenium
      - Ausreichend HTML-Text → direkte Auslieferung ohne Selenium
      - JS/SPAs/CMP erkannt → Start mit Selenium (Standard-Strategie `speed`, konfigurierbar via `js_strategy`)
    
    ### `fast` - Schneller HTTP-Modus
    - **Ideal für**: Statische Webseiten, Dokumenten-Downloads, APIs
    - **Unterstützt**: HTML, PDF, DOCX, PPTX, XLSX, Bilder, Text-Dateien
    - **Features**: HTTP/2, automatische Redirects, Cookie-Persistenz, Proxy-Support
    - **Performance**: Sehr schnell (1-5 Sekunden), ressourcenschonend
    - **Limitierungen**: Kein JavaScript-Rendering, keine dynamischen Inhalte
    
    ### `js` - Browser-Rendering-Modus  
    - **Ideal für**: Single-Page-Applications, JavaScript-abhängige Seiten, moderne Web-Apps
    - **Engine**: Selenium Chrome WebDriver mit Stealth-Features
    - **Features**: Vollständiges Browser-Verhalten, Cookie-Banner-Klick, DOM-Warten
    - **Performance**: Langsamer (5-30 Sekunden), höherer Ressourcenverbrauch
    - **Vorteile**: Rendert JavaScript, wartet auf dynamische Inhalte
    
    ## JS-Strategie (optional)
    Steuerung der Warte-/Stabilitäts-Heuristiken im JS-Modus über `js_strategy` (Standard: `speed`):
    
    - `speed` (Standard):
      - Aggressive Verkürzung der Waits mit Polling aller Selektoren pro Tick und Early-Exit
      - Sehr kurze SPA/Loader/Progressive-Caps, best-effort; geeignet für schnelle Scans/Batchläufe
    - `accuracy`:
      - Maximale Qualität/Robustheit, mit leicht aggressiveren Caps als zuvor
    
    ## 🔧 Schema-Overrides (pro Request)
    Optional können Standardwerte aus der .env pro Request überschrieben werden:
    - `html_converter`: "trafilatura" | "markitdown" | "bs4" (Default aus .env)
    - `trafilatura_clean_markdown`: true | false | null (null = .env-Default)
    - `media_conversion_policy`: "skip" | "metadata" | "full" | "none" (Default: "skip")
      - Hinweis: "none" erzeugt keinerlei Markdown-Ausgabe für Medien
    - `allow_insecure_ssl`: true | false | null (null = .env-Default)

    ## 📄 Unterstützte Formate:
    - **Web**: HTML, XHTML, XML, RSS/Atom-Feeds
    - **Office**: DOCX, PPTX, XLSX, ODT, ODS, ODP
    - **PDF**: Alle PDF-Versionen mit Text-Extraktion
    - **Bilder**: JPG, PNG, GIF, WebP, SVG (mit OCR-Unterstützung)
    - **Text**: TXT, CSV, JSON, Markdown, RTF
    - **Code**: Syntax-Highlighting für alle gängigen Programmiersprachen
    
    ## 🤖 LLM-Nachbearbeitung (Optional):
    
    **Voraussetzung**: OpenAI API-Key in Umgebungsvariablen konfiguriert
    
    ### Automatische Bereinigung:
    - Entfernt Navigation, Werbung, Cookie-Banner, Footer
    - Korrigiert Markdown-Struktur und Formatierung  
    - Arbeitet den relevanten Inhaltskern heraus
    - Klassifiziert Content: "Bildungsinhalt", "Metabeschreibung", "Fehler/Infoseite"
    
    ### Erweiterte Features:
    - **Custom Prompts**: Zusätzliche Bereinigungsanweisungen
    - **Anonymisierung**: Automatische Entfernung personenbezogener Daten
    - **Mehrsprachigkeit**: Übersetzung und Lokalisierung
    - **Zusammenfassung**: Komprimierung langer Texte
    
    ## 🔗 Link-Extraktion:
    Kategorisiert automatisch alle gefundenen Links:
    - **content**: Artikel, Ressourcen, Hauptinhalte
    - **nav**: Navigation, Menüs, Breadcrumbs
    - **social**: Social Media, Sharing-Buttons
    - **auth**: Login, Registrierung, Account-Bereiche
    - **legal**: Impressum, Datenschutz, AGB
    - **search**: Suchfunktionen, Filter
    - **contact**: Kontakt-Informationen, Support
    - **download**: Download-Links, Attachments
    - **anchor**: Interne Anker-Links (#section)
    - **other**: Sonstige Links
    
    ## ⚡ Performance & Sicherheit:
    - **Timeout-Kontrolle**: Konfigurierbare Zeitlimits (1s-10min)
    - **Retry-Mechanismus**: Automatische Wiederholung bei Fehlern
    - **Größen-Limits**: Schutz vor zu großen Downloads
    - **Proxy-Support**: HTTP/HTTPS/SOCKS mit Authentifizierung
    - **Anti-Bot-Umgehung**: Stealth-Features, User-Agent-Rotation
    - **Ressourcen-Pool**: Effiziente Browser-Wiederverwendung
    
    ## 📊 Response-Format:
    - **Original-Content**: Unbearbeiteter Markdown im `markdown`-Feld
    - **LLM-Bereinigung**: Bereinigte Version im `llm.cleaned_markdown`-Feld  
    - **Metadaten**: Status-Codes, Redirects, Content-Types, Timing
    - **Link-Analyse**: Strukturierte Link-Liste mit Kategorisierung
    - **Fehler-Erkennung**: Automatische Erkennung von 404/403/500-Seiten
    
    **Kosten**: LLM-Features verbrauchen OpenAI-Tokens (~0.01-0.10$ pro Request)
    **Dauer**: Fast-Modus 1-5s, JS-Modus 5-30s, +LLM 2-10s
    """
    ua = pick_user_agent(settings.default_user_agent)
    timeout_ms = req.timeout_ms or (settings.default_timeout_seconds * 1000)
    timeout_s = max(1, int((timeout_ms + 999) // 1000))
    retries = req.retries if req.retries is not None else settings.default_retries
    max_bytes = req.max_bytes or settings.default_max_bytes
    proxy_norm = normalize_proxy(req.proxy)

    t0 = time.perf_counter()
    try:
        if req.mode == "fast":
            status, final_url, data, ctype = await fetch_with_httpx(
                url=str(req.url),
                timeout_seconds=timeout_s,
                retries=retries,
                proxy=proxy_norm,
                user_agent=ua,
                max_bytes=max_bytes,
                allow_insecure_ssl=req.allow_insecure_ssl,
            )
        elif req.mode == "auto":
            # Lightweight preflight to pick best path quickly
            pf = await preflight_analyze(
                str(req.url),
                timeout_seconds=min(timeout_s, 12),
                user_agent=ua,
                allow_insecure_ssl=req.allow_insecure_ssl,
            )
            strat = pf.get("strategy")
            # Direct return cases without Selenium
            if strat in {"PDF", "RSS", "HTTP_ONLY", "YOUTUBE"}:
                status = pf.get("status", 200)
                final_url = pf.get("final_url", str(req.url))
                data = pf.get("content_bytes") or (pf.get("html_text") or "").encode("utf-8")
                ctype = pf.get("content_type") or ("text/html; charset=utf-8" if pf.get("html_text") else None)
            else:
                # JS paths: JS_LIGHT / JS_LIGHT_CONSENT / HTTP_THEN_JS
                if strat == "HTTP_THEN_JS" and (pf.get("features", {}).get("text_len", 0) >= 700):
                    # Good enough without JS
                    status = pf.get("status", 200)
                    final_url = pf.get("final_url", str(req.url))
                    data = pf.get("content_bytes") or (pf.get("html_text") or "").encode("utf-8")
                    ctype = pf.get("content_type") or "text/html; charset=utf-8"
                else:
                    # Run Selenium for JS_LIGHT and friends; respect provided js_strategy
                    js_strategy = req.js_strategy or "speed"
                    js_auto_wait = settings.default_js_auto_wait
                    wait_selectors = [
                        "article", "main", "#content", "#main-content", "[role=main]"
                    ] if js_auto_wait else None
                    wait_ms = 1500 if js_auto_wait else None
                    status, final_url, data, ctype = await fetch_with_playwright(
                        url=str(req.url),
                        timeout_seconds=timeout_s,
                        retries=retries,
                        proxy=proxy_norm,
                        user_agent=ua,
                        max_bytes=max_bytes,
                        headless=True,
                        stealth=True,
                        wait_for_selectors=wait_selectors,
                        wait_for_ms=wait_ms,
                        js_strategy=js_strategy,
                    )
        else:
            # JS defaults: headless+stealth always on; optional auto waits from config
            js_auto_wait = settings.default_js_auto_wait
            wait_selectors = ["article", "main", "#content", "#main-content", "[role=main]"] if js_auto_wait else None
            wait_ms = 2000 if js_auto_wait else None
            # Determine JS strategy (accuracy|speed)
            js_strategy = req.js_strategy or settings.default_js_strategy
            status, final_url, data, ctype = await fetch_with_playwright(
                url=str(req.url),
                timeout_seconds=timeout_s,
                retries=retries,
                proxy=proxy_norm,
                user_agent=ua,
                max_bytes=max_bytes,
                headless=True,
                stealth=True,
                wait_for_selectors=wait_selectors,
                wait_for_ms=wait_ms,
                js_strategy=js_strategy,
            )
    except Exception as e:
        msg = str(e) or repr(e)
        logger.error(f"Fetch error for {req.url}: {type(e).__name__}: {msg}")
        # Map specific error types to more precise status codes
        status_code = 502
        low = msg.lower()
        if isinstance(e, (httpx.ReadTimeout, httpx.ConnectTimeout)) or "timeout" in low:
            status_code = 504  # Gateway Timeout / upstream timeout
        elif isinstance(e, WebDriverException) and ("timed out receiving message from renderer" in low):
            status_code = 504
        elif isinstance(e, httpx.ConnectError):
            status_code = 502  # Bad Gateway / upstream connect error
        raise HTTPException(status_code=status_code, detail=f"Fetch error: {type(e).__name__}: {msg}")

    # Convert to markdown with error handling
    try:
        markdown = bytes_to_markdown(
            data,
            content_type=ctype,
            url=str(req.url),
            html_converter=req.html_converter,
            trafilatura_clean_markdown=req.trafilatura_clean_markdown,
            media_conversion_policy=req.media_conversion_policy,
        )
    except Exception as e:
        logger.error(f"Markdown conversion failed for {req.url}: {e}")
        # Return a meaningful error response instead of crashing
        markdown = f"# Content Conversion Failed\n\nFailed to convert content from {req.url}\n\nError: {str(e)}\n\nThis may be due to a corrupted file, unsupported format, or network issue."

    # Optional link extraction (only for HTML-like data)
    links = None
    if req.extract_links and (ctype or "").lower().startswith("text/html"):
        try:
            html_text = data.decode("utf-8", errors="ignore")
            details = extract_links_detailed_from_html(html_text, final_url)
            links = [LinkInfo(**d) for d in details]
        except Exception:
            links = None

    # Error-page detection
    err = detect_error_page(markdown, status)

    # Optional LLM post-processing
    llm_payload = None
    if req.llm_postprocess:
        api_key = settings.llm_api_key
        if not api_key:
            # Do not fail the entire request if LLM is not configured
            logger.warning("LLM postprocess requested but LLM_API_KEY is not configured. Skipping LLM step.")
            api_key = None
        try:
            if api_key:
                cleaned, cls, anonymized, tokens = await postprocess_markdown_async(
                    markdown=markdown,
                    base_url=final_url,
                    api_key=api_key,
                    model=settings.llm_model or "gpt-5-mini",
                    base=settings.llm_base_url,
                    clean_prompt=req.llm_clean_prompt,
                    anonymize=req.llm_anonymize,
                )
                llm_payload = LLMResult(
                    cleaned_markdown=cleaned,
                    classification=cls,  # type: ignore[arg-type]
                    anonymized=anonymized,
                    tokens_used=tokens,
                )
                # Keep original markdown in main field, cleaned version only in llm field
        except Exception as e:
            # Never escalate LLM errors to a 500 for the whole crawl
            msg = str(e) or repr(e)
            logger.error(f"LLM postprocess error: {type(e).__name__}: {msg}")

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    resp = CrawlResponse(
        request_mode=req.mode,
        requested_url=str(req.url),
        final_url=final_url,
        status_code=status,
        redirected=(final_url.rstrip('/') != str(req.url).rstrip('/')),
        content_type=ctype,
        markdown=markdown,
        markdown_length=len(markdown or ""),
        error_page_detected=err,
        links=links,
        llm=llm_payload,
        elapsed_ms=elapsed_ms,
    )
    return resp
