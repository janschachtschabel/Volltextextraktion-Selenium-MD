from __future__ import annotations

import time
from fastapi import FastAPI, HTTPException

from .config import settings
from .schemas import CrawlRequest, CrawlResponse, LLMResult, LinkInfo
from .http_fetcher import fetch_with_httpx
from .preflight import preflight as preflight_analyze
from .js_fetcher import fetch_with_playwright, cleanup_drivers
from .converter import bytes_to_markdown
from .utils import detect_error_page, extract_links_detailed_from_html, normalize_proxy, pick_user_agent
from .llm import postprocess_markdown
import sys
import asyncio

# No special event loop policy needed - subprocess approach handles this


app = FastAPI(title="Volltextextraktion Selenium MD", version="0.1.0")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up Selenium drivers on shutdown."""
    cleanup_drivers()


@app.get("/")
async def root():
    return {"status": "ok"}


@app.post("/crawl", response_model=CrawlResponse)
async def crawl(req: CrawlRequest):
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
            )
        elif req.mode == "auto":
            # Lightweight preflight to pick best path quickly
            pf = await preflight_analyze(str(req.url), timeout_seconds=min(timeout_s, 12), user_agent=ua)
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
        raise HTTPException(status_code=502, detail=f"Fetch error: {type(e).__name__}: {msg}")

    # Convert to markdown
    markdown = bytes_to_markdown(data, content_type=ctype, url=str(req.url))

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
            raise HTTPException(status_code=500, detail="LLM_API_KEY not configured in environment")
        try:
            cleaned, cls, anonymized, tokens = postprocess_markdown(
                markdown=markdown,
                base_url=final_url,
                api_key=api_key,
                model=settings.llm_model or "gpt-4.1-mini",
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
            msg = str(e) or repr(e)
            raise HTTPException(status_code=500, detail=f"LLM postprocess error: {type(e).__name__}: {msg}")

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
