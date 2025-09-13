from __future__ import annotations

from typing import Literal, Optional, List
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class CrawlRequest(BaseModel):
    """
    Request-Schema für das Crawlen von Webseiten mit automatischer Markdown-Konvertierung.
    
    Unterstützt drei Modi:
    - 'fast': Schneller HTTP-Abruf für statische Inhalte
    - 'js': Browser-Rendering für JavaScript-abhängige Seiten
    - 'auto': Pre-Flight-Analyse entscheidet zwischen HTTP_ONLY, JS_LIGHT oder Spezialpfaden
    """
    # OpenAPI Beispiel (Standardvorgaben im Docs-Endpoint)
    model_config = ConfigDict(
        json_schema_extra={
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
                "max_bytes": 1048576
            }
        }
    )
    
    url: HttpUrl = Field(
        description="Die zu crawlende URL",
        examples=["https://example.com", "https://docs.python.org/3/tutorial/"]
    )

    # HTML/Markdown Konvertierung (Schema-basierte Overrides)
    html_converter: Optional[Literal["trafilatura", "markitdown", "bs4"]] = Field(
        default=None,
        description=(
            "HTML→Markdown Konverter für diesen Request.\n"
            "• trafilatura (Default in .env): Robuste Kerninhalts-Extraktion\n"
            "• markitdown: Volle HTML→Markdown-Konvertierung\n"
            "• bs4: Einfache Text-Extraktion (nur HTML)"
        ),
        examples=[None, "trafilatura", "markitdown", "bs4"],
    )

    trafilatura_clean_markdown: Optional[bool] = Field(
        default=None,
        description=(
            "Trafilatura Ausgabe-Modus: True=bereinigtes Markdown (Hauptinhalt), False=roh (html2txt).\n"
            "Wenn None, wird der .env-Default (TRAFILATURA_CLEAN_MARKDOWN) verwendet."
        ),
        examples=[None, True, False],
    )

    media_conversion_policy: Optional[Literal["skip", "metadata", "full", "none"]] = Field(
        default=None,
        description=(
            "Medien-Konvertierung für Audio/Video:\n"
            "• skip (Default): keine Konvertierung, nur Platzhalter-Hinweis\n"
            "• metadata: nur ffprobe-Metadaten als JSON\n"
            "• full: vollständige Konvertierung (langsam)\n"
            "• none: gar keine Konvertierungstexte (minimaler Platzhalter)"
        ),
        examples=[None, "skip", "metadata", "full", "none"],
    )

    allow_insecure_ssl: Optional[bool] = Field(
        default=None,
        description=(
            "SSL-Validierung für diesen Request deaktivieren (verify=false).\n"
            "Wenn None, wird der .env-Default (ALLOW_INSECURE_SSL) verwendet."
        ),
        examples=[None, True, False],
    )
    
    mode: Literal["fast", "js", "auto"] = Field(
        default="auto", 
        description="""Crawl-Modus auswählen:
        
• fast: Schneller HTTP-Abruf mit httpx
  - Für statische HTML-Seiten, PDFs, Office-Dokumente
  - HTTP/2, automatische Redirects, Cookie-Persistenz
  - Schnell und ressourcenschonend
  
• js: Browser-Rendering mit Selenium Chrome
  - Für JavaScript-abhängige Single-Page-Applications
  - Wartet auf DOM-Inhalte, klickt Cookie-Banner weg
  - Langsamer, aber vollständiges Browser-Verhalten

• auto: Pre-Flight-Analyse (httpx + HTML-Parsing) wählt automatisch die beste Strategie
  - HTTP_ONLY: direktes HTML (kein Selenium)
  - JS_LIGHT: Selenium mit aggressivem "speed"-Profil (Assets blocken, kurze Waits)
  - Spezialfälle: PDF/RSS/YouTube werden ohne Selenium behandelt""",
        examples=["auto", "fast", "js"]
    )
    
    js_strategy: Literal["accuracy", "speed"] = Field(
        default="speed",
        description="""Strategie für den JS-Modus (Selenium):
        
• speed (Standard): aggressive Beschleunigung mit kurzen Caps und parallelen Waits (best effort)
• accuracy: maximale Qualität/Robustheit; leicht aggressivere Caps als zuvor
""",
        examples=["accuracy", "speed"]
    )
    
    timeout_ms: int = Field(
        default=180_000, ge=1000, le=600_000,
        description="""Timeout in Millisekunden (1-600 Sekunden):
        
• **fast-Modus**: HTTP-Request-Timeout
• **js-Modus**: Browser-Navigation + Warte-Zeit für Inhalte

Empfohlene Werte:
- Schnelle Seiten: 30.000ms (30s)
- Normale Seiten: 180.000ms (3min) 
- Langsame JS-Apps: 300.000ms (5min)""",
        examples=[30000, 180000, 300000]
    )
    
    retries: int = Field(
        default=2, ge=0, le=10, 
        description="""Anzahl Wiederholungsversuche bei Fehlern:
        
• 0: Keine Wiederholung
• 1-3: Empfohlen für normale Seiten  
• 4-10: Für instabile/überlastete Server

Wiederholung erfolgt bei: Netzwerkfehlern, Timeouts, 5xx-Serverfehler""",
        examples=[0, 2, 5]
    )
    
    proxy: Optional[str] = Field(
        default=None, 
        description="""Optionaler Proxy-Server:
        
Unterstützte Formate:
• HTTP: `http://proxy.example.com:8080`
• HTTPS: `https://proxy.example.com:8080` 
• Mit Auth: `http://user:pass@proxy.example.com:8080`
• SOCKS: `socks5://proxy.example.com:1080`

**Hinweis**: Wird ignoriert wenn leer oder der Platzhalter "string" verwendet wird""",
        examples=[None, "http://proxy.example.com:8080", "http://user:pass@proxy.example.com:8080"]
    )
    
    max_bytes: int = Field(
        default=10 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024,
        description="""Maximale Dateigröße in Bytes:
        
Verhindert zu große Downloads und schützt vor Speicher-Problemen.

Empfohlene Werte:
• Kleine Seiten: 1.048.576 (1MB)
• Standard: 10.485.760 (10MB)
• Große Dokumente: 52.428.800 (50MB)

**Hinweis**: Download stoppt bei Erreichen des Limits""",
        examples=[1048576, 10485760, 52428800]
    )
    
    extract_links: bool = Field(
        default=False, 
        description="""Link-Extraktion für HTML-Inhalte:
        
Bei aktivierter Option werden alle Links der Seite extrahiert und kategorisiert:

**Kategorien:**
• content: Inhaltliche Links (Artikel, Ressourcen)
• nav: Navigation (Menü, Breadcrumbs)  
• social: Social Media Links
• auth: Login/Registrierung
• legal: Impressum, Datenschutz
• search: Suchfunktionen
• contact: Kontakt-Informationen
• download: Download-Links
• anchor: Anker-Links (#section)
• other: Sonstige Links

**Zusätzliche Infos**: URL, Link-Text, internal/external""",
        examples=[False, True]
    )

    # Optional LLM-Nachbearbeitung
    llm_postprocess: bool = Field(
        default=False, 
        description="""Strukturelle Bereinigung & Fokussierung auf Inhalte aktivieren (LLM):
• Entfernt Navigation/Ads/Banner
• Struktur verbessert Markdown & Fokus auf Kerninhalte
• Optional: Klassifizierung

Voraussetzung: LLM_API_KEY in .env""",
        examples=[False, True]
    )
    
    llm_anonymize: bool = Field(
        default=False, 
        description="""Personenbezogene Daten entfernen/ersetzen (PII-Anonymisierung).
Nur aktiv, wenn llm_postprocess=true.""",
        examples=[False, True]
    )
    
    llm_clean_prompt: Optional[str] = Field(
        default=None, 
        description="""Custom-Anweisungen für die LLM-Bereinigung (optional), z. B.:
• "Entferne Datumsangaben"
• "Fokussiere nur auf Code-Beispiele"
• "Fasse in 3 Sätzen zusammen"

Nur aktiv, wenn llm_postprocess=true.""",
        examples=[
            None,
            "Entferne alle Datumsangaben",
            "Fokussiere nur auf Code-Beispiele", 
            "Fasse in 3 Sätzen zusammen"
        ]
    )


class LinkInfo(BaseModel):
    """Informationen über einen extrahierten Link."""
    url: str = Field(description="Vollständige URL des Links")
    text: Optional[str] = Field(default=None, description="Angezeigter Link-Text")
    internal: bool = Field(description="True wenn Link zur gleichen Domain gehört")
    category: Literal[
        "content",
        "social", 
        "nav",
        "auth",
        "legal",
        "search",
        "contact",
        "download",
        "anchor",
        "other",
    ] = Field(default="other", description="Automatisch erkannte Link-Kategorie")


class LLMResult(BaseModel):
    """Ergebnis der LLM-Nachbearbeitung."""
    cleaned_markdown: str = Field(description="Bereinigter und strukturierter Markdown-Text")
    classification: Literal[
        "Bildungsinhalt",
        "Metabeschreibung", 
        "Fehler/Infoseite",
    ] = Field(default="Metabeschreibung", description="Automatische Inhalts-Klassifizierung")
    anonymized: bool = Field(default=False, description="Ob personenbezogene Daten anonymisiert wurden")
    tokens_used: int | None = Field(default=None, description="Anzahl verbrauchter OpenAI-Tokens")


class CrawlResponse(BaseModel):
    """
    Antwort-Schema für Crawl-Requests.
    
    Enthält sowohl die ursprünglichen Rohdaten als auch optional bereinigte LLM-Ergebnisse.
    """
    request_mode: Literal["fast", "js", "auto"] = Field(description="Verwendeter Crawl-Modus")
    requested_url: str = Field(description="Ursprünglich angeforderte URL")
    final_url: str = Field(description="Finale URL nach Redirects")
    status_code: int = Field(description="HTTP-Status-Code (200, 404, etc.)")
    redirected: bool = Field(description="Ob Redirects aufgetreten sind")
    content_type: str | None = Field(description="MIME-Type der Antwort (text/html, application/pdf, etc.)")
    markdown: str = Field(description="Originaler Markdown-Inhalt (unbearbeitet)")
    markdown_length: int = Field(description="Länge des Markdown-Texts in Zeichen")
    error_page_detected: bool = Field(description="Ob eine Fehlerseite erkannt wurde (404, 403, etc.)")
    links: Optional[list[LinkInfo]] = Field(default=None, description="Extrahierte Links (nur wenn extract_links=true)")
    llm: Optional[LLMResult] = Field(default=None, description="LLM-Nachbearbeitung (nur wenn llm_postprocess=true)")
    elapsed_ms: int = Field(description="Gesamtdauer des Requests in Millisekunden")
