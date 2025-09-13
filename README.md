#### HTML‑Konvertierung (NEU)

- `HTML_CONVERTER` (Standard: `trafilatura`)
  - `trafilatura`: Extrahiert den Inhaltskern robust und schnell. Fallback‑Kette: Trafilatura → MarkItDown → BS4.
  - `markitdown`: Vollständige HTML→Markdown‑Konvertierung. Fallback: BS4.
  - `bs4`: Einfache Text‑Extraktion via BeautifulSoup (nur HTML).

- `TRAFILATURA_CLEAN_MARKDOWN` (Standard: `true`)
  - `true` → „Bereinigtes“ Markdown via `trafilatura.extract(output_format='markdown')` (fokussiert auf Hauptinhalt)
  - `false` → Roh‑Extraktion via `trafilatura.html2txt()` (Plain‑Text, Markdown‑kompatibel)

Per‑Request Override über das Schema (`POST /crawl`):

- `html_converter`: `"trafilatura" | "markitdown" | "bs4"` (überschreibt `.env` für den Request)
- `trafilatura_clean_markdown`: `true|false|null` (bei `null` gilt `.env`‑Default)
- `media_conversion_policy`: `"skip" | "metadata" | "full" | "none"` (Standard: `skip`)
  - `none` → keinerlei Medien‑Ausgabe (leerer String), nützlich für strikt textuelle Pipelines
- `allow_insecure_ssl`: `true|false|null` (überschreibt SSL‑Prüfung für HTTP‑Pfad; `null` nutzt `.env`)

Hinweise:
- Nach Trafilatura‑Extraktion werden weiterhin unsere Nachbearbeitungen angewandt: `preserve_mathematical_content()` und `enhance_table_structure()` aus `app/converter.py`.
- Bei HTML‑Problemen liefert die Kette verlässlich einen Output: Trafilatura (wenn aktiv) → MarkItDown (sofern nicht deaktiviert/ausgefallen) → BS4‑Fallback.

### Schnelle Referenz: .env Parameter

| Name | Typ/Werte | Standard | Hinweis |
|---|---|---|---|
| HOST | string | 0.0.0.0 | Bind-Adresse |
| PORT | int | 8000 | API-Port |
| DEFAULT_MODE | auto|fast|js | auto | Default Crawl‑Modus |
| DEFAULT_TIMEOUT_SECONDS | int 1–600 | 180 | Gesamtbudget pro Request |
| DEFAULT_RETRIES | int 0–10 | 2 | Wiederholungen bei Fehlern |
| DEFAULT_MAX_BYTES | int 1024–104857600 | 10485760 | Max. Antwortgröße |
| DEFAULT_JS_STRATEGY | speed|accuracy | speed | JS-Modus Default |
| SELENIUM_POOL_SIZE | int ≥1 | 2 | Startgröße Driver-Pool |
| SELENIUM_MAX_POOL_SIZE | int ≥POOL_SIZE | 8 | Auto-Scaling Obergrenze |
| SELENIUM_SCALE_THRESHOLD | float 0.0–1.0 | 0.8 | Scale-Up Schwellwert |
| MAX_CONCURRENT_REQUESTS | int ≥1 | 8 | Parallelität API |
| MAX_QUEUE_SIZE | int ≥0 | 50 | Queue-Länge |
| QUEUE_TIMEOUT_SECONDS | int ≥0 | 60 | Queue-Wartezeit |
| MEDIA_CONVERSION_POLICY | skip|metadata|full|none | skip | Medienverarbeitung (Default) |
| HTML_CONVERTER | trafilatura|markitdown|bs4 | trafilatura | HTML‑Konverter & Fallback‑Kette |
| TRAFILATURA_CLEAN_MARKDOWN | true|false | true | Trafilatura: bereinigtes Markdown vs. Roh‑Text |
| ALLOW_INSECURE_SSL | true|false | false | Zertifikatsprüfung abschalten |
| LLM_BASE_URL | url | https://api.openai.com/v1 | OpenAI-kompatibel |
| LLM_MODEL | string | gpt-5-mini | Modellname |
| LLM_API_KEY | string | — | oder OPENAI_API_KEY |

# Volltextextraktion Selenium MD

Ein schlankes FastAPI-Projekt zum asynchronen Crawlen von Webseiten und automatischen Umwandeln in Markdown mit `markitdown[all]`. Optional mit LLM-Nachbearbeitung (OpenAI, gpt-5-mini).

## Features

- Drei Modi:
  - "fast": schneller Abruf via `httpx` (HTTP/2, Redirect-Following, Connection-Pooling, Cookie-Persistenz)
  - "js": Rendering via `Selenium` (Headless, Stealth, Cookie-Banner-Klick, CSS-Selector-Waits)
  - "auto": Preflight-Analyse (httpx + HTML-Parsing) entscheidet automatisch zwischen HTTP_ONLY, JS_LIGHT oder Spezialpfaden (PDF/RSS/YouTube)
- Automatische Markdown-Konvertierung aller von `markitdown` unterstützten Formate (HTML, PDF, DOCX, PPTX, XLSX, Bilder, …)
- Parameter: Timeout (default 180s), Retries (default 2), Headless, Proxy, Stealth, `max_bytes` (Dateigrößenlimit)
- Anti-Bot/Cloudflare (best effort), Cookie-Banner-Handhabung (best effort)
- Fehlerseitenerkennung, optionale Link-Extraktion (bei HTML)
- Rückgabe enthält Statuscode, finale URL, Zeichenanzahl des Markdown
- Optional: LLM-Postprocessing (Bereinigung, Anonymisierung, Klassifizierung), konfigurierbar via `.env`

## Installation 🛠️

### Windows

```powershell
# 1. Clone/Download das Projekt
git clone <repo-url>
cd Volltextextraktion-Selenium-MD

# 2. Virtual Environment (empfohlen)
python -m venv .venv
.venv\Scripts\activate

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Environment-Datei kopieren und anpassen
copy .env.example .env
# .env editieren: LLM_API_KEY setzen falls gewünscht

# 5. API starten
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**✅ Selenium-basiert:** Verwendet Chrome WebDriver mit automatischer Installation über webdriver-manager.

API dann unter: http://127.0.0.1:8000

## API

POST `/crawl`

Request-Body (vollständiges Schema, Standard: mode="auto"):

```json
{
  "url": "https://example.com",
  "mode": "auto",
  "js_strategy": "speed",
  "html_converter": "trafilatura",
  "trafilatura_clean_markdown": true,
  "media_conversion_policy": "skip",
  "allow_insecure_ssl": true,
  "extract_links": false,
  "llm_postprocess": false,
  "llm_anonymize": false,
  "llm_clean_prompt": null,
  "retries": 2,
  "timeout_ms": 30000,
  "max_bytes": 1048576
}
```

## Parameter-Erklärungen

### Basis-Parameter

**`url`** (erforderlich)
- Die zu crawlende URL
- Beispiele: `https://example.com`, `https://docs.python.org/3/tutorial/`

**`mode`** (Standard: `"auto"`)
- **`"fast"`**: Schneller HTTP-Abruf mit httpx
  - Für statische HTML-Seiten, PDFs, Office-Dokumente
  - HTTP/2, automatische Redirects, Cookie-Persistenz
  - Schnell und ressourcenschonend
- **`"js"`**: Browser-Rendering mit Selenium Chrome
  - Für JavaScript-abhängige Single-Page-Applications
  - Wartet auf DOM-Inhalte, klickt Cookie-Banner weg
  - Langsamer, aber vollständiges Browser-Verhalten
- **`"auto"`**: Preflight-Analyse (httpx + BeautifulSoup)
  - Erkennt PDF/RSS/YouTube und liefert direkt ohne Selenium aus
  - Erkennt HTML mit ausreichendem Text → liefert direkt ohne Selenium aus
  - Erkennt JS/SPAs/CMP → startet Selenium mit `js_strategy` (Standard: `speed`)

**`js_strategy`** (bei `mode: "js"` oder wenn `mode: "auto"` JS benötigt, Standard: `"speed"`)
- Steuert die Warte- und Stabilitäts-Strategie:
  - `speed` (Standard): aggressive Verkürzung (Polling aller Selektoren mit Early‑Exit, kurze Caps), best effort
  - `accuracy`: maximale Qualität/Robustheit; leicht aggressivere Caps als zuvor

**`timeout_ms`** (Standard: `180000` = 3 Minuten)
- Timeout in Millisekunden (1.000-600.000)
- **fast-Modus**: HTTP-Request-Timeout
- **js-Modus**: Browser-Navigation + Warte-Zeit für Inhalte
- Empfohlene Werte:
  - Schnelle Seiten: `30000` (30s)
  - Normale Seiten: `180000` (3min)
  - Langsame JS-Apps: `300000` (5min)

**`retries`** (Standard: `2`)
- Anzahl Wiederholungsversuche bei Fehlern (0-10)
- Wiederholung erfolgt bei: Netzwerkfehlern, Timeouts, 5xx-Serverfehler
- Empfohlene Werte:
  - Stabile Seiten: `0-1`
  - Normale Seiten: `2-3`

**`proxy`** (Standard: `null`)
- Optionaler Proxy-Server
- Unterstützte Formate:
  - HTTP: `"http://proxy.example.com:8080"`
  - HTTPS: `"https://proxy.example.com:8080"`
  - Mit Auth: `"http://user:pass@proxy.example.com:8080"`
  - SOCKS: `"socks5://proxy.example.com:1080"`
- Wird ignoriert wenn leer oder `"string"`

**`max_bytes`** (Standard: `10485760` = 10MB)
- Maximale Dateigröße in Bytes (1.024-104.857.600)
- Verhindert zu große Downloads und Speicher-Probleme
- Empfohlene Werte:
  - Kleine Seiten: `1048576` (1MB)
  - Standard: `10485760` (10MB)
  - Große Dokumente: `52428800` (50MB)

**`extract_links`** (Standard: `false`)
- Link-Extraktion für HTML-Inhalte aktivieren
- Extrahiert und kategorisiert alle Links der Seite
- **Kategorien**: `content`, `nav`, `social`, `auth`, `legal`, `search`, `contact`, `download`, `anchor`, `other`
- **Zusätzliche Infos**: URL, Link-Text, internal/external

### LLM-Parameter (OpenAI-Integration)

**Voraussetzung**: `LLM_API_KEY` oder `OPENAI_API_KEY` in `.env` konfiguriert (oder als Systemumgebungsvariable)

**`llm_postprocess`** (Standard: `false`)
- **Hauptschalter** für LLM-Nachbearbeitung
- **Ohne diese Option**: Kein LLM wird verwendet, egal was andere Parameter sagen
- **Automatische Funktionen**:
  - Markdown bereinigen und strukturieren
  - Navigation, Werbung, Cookie-Banner entfernen
  - Inhaltskern herausarbeiten
  - Klassifizierung: "Bildungsinhalt", "Metabeschreibung", "Fehler/Infoseite"
- **Kosten**: Verbraucht OpenAI API-Tokens
- **Dauer**: +2-10 Sekunden je nach Textlänge

**`llm_clean_prompt`** (Standard: `null`)
- **Zusätzliche Anweisungen** für LLM-Bereinigung
- **Nur aktiv wenn**: `llm_postprocess: true`
- **Standard-Bereinigung** läuft immer automatisch, dies sind **zusätzliche** Anweisungen
- **Beispiele**:
  ```json
  "llm_clean_prompt": "Entferne alle Datumsangaben und Autorennamen"
  "llm_clean_prompt": "Fokussiere nur auf Code-Beispiele und technische Inhalte"
  "llm_clean_prompt": "Fasse den Inhalt in maximal 3 Absätzen zusammen"
  "llm_clean_prompt": "Übersetze englische Begriffe ins Deutsche"
  ```

**`llm_anonymize`** (Standard: `false`)
- **Personenbezogene Daten anonymisieren**
- **Nur aktiv wenn**: `llm_postprocess: true`
- **Entfernt/ersetzt automatisch**:
  - Namen von Personen → `[Name]`
  - E-Mail-Adressen → `[E-Mail]`
  - Telefonnummern → `[Telefon]`
  - Adressen → `[Adresse]`
  - Andere persönliche Identifikatoren
- **Hinweis**: KI-basierte Erkennung, 100% Genauigkeit nicht garantiert

### LLM-Parameter Zusammenspiel

```json
// Nur Standard-Bereinigung
{
  "llm_postprocess": true,
  "llm_clean_prompt": null,
  "llm_anonymize": false
}

// Standard-Bereinigung + zusätzliche Anweisungen
{
  "llm_postprocess": true,
  "llm_clean_prompt": "Entferne alle Datumsangaben",
  "llm_anonymize": false
}

// Standard-Bereinigung + Anonymisierung
{
  "llm_postprocess": true,
  "llm_clean_prompt": null,
  "llm_anonymize": true
}

// Alles kombiniert
{
  "llm_postprocess": true,
  "llm_clean_prompt": "Fokus auf technische Inhalte",
  "llm_anonymize": true
}

// Kein LLM (andere Parameter werden ignoriert)
{
  "llm_postprocess": false,
  "llm_clean_prompt": "wird ignoriert",
  "llm_anonymize": true // wird ignoriert
}
```

### Konfiguration über .env

Einige Parameter können über `.env`-Datei vorkonfiguriert werden:

#### Basis-Einstellungen
- `DEFAULT_TIMEOUT_SECONDS`: Standard-Timeout
- `DEFAULT_RETRIES`: Standard-Wiederholungen
- `DEFAULT_MAX_BYTES`: Standard-Dateigröße-Limit
- `DEFAULT_USER_AGENT`: Browser User-Agent für Selenium
- `DEFAULT_JS_AUTO_WAIT`: Automatische Wartezeiten im JS-Modus
- `DEFAULT_JS_STRATEGY`: Voreinstellung für die JS‑Strategie (`accuracy|speed`)
- `DEFAULT_MODE`: Voreinstellung für den Crawl‑Modus (`auto|fast|js`, Standard: `auto`)

#### Selenium Pool & Kapazität (NEU)
- `SELENIUM_POOL_SIZE`: Anfangs-Anzahl Chrome-Driver im Pool (Standard: 2)
- `SELENIUM_MAX_POOL_SIZE`: Maximale Pool-Größe bei hoher Last (Standard: 8)
- `SELENIUM_SCALE_THRESHOLD`: Auslastungsgrenze für Pool-Skalierung (Standard: 0.8 = 80%)
- `MAX_CONCURRENT_REQUESTS`: Maximale gleichzeitige Requests (Standard: 8)
- `MAX_QUEUE_SIZE`: Warteschlangen-Kapazität für überschüssige Requests (Standard: 50)
- `QUEUE_TIMEOUT_SECONDS`: Maximale Wartezeit in der Queue (Standard: 60s)

#### Medien-Handling (NEU)

- `MEDIA_CONVERSION_POLICY` (Standard: `skip`)
  - `skip`: Audio/Video werden nicht konvertiert. Es wird ein kurzer Platzhalter‑Markdown mit Content‑Type und optionaler Quelle zurückgegeben. Schnell und ressourcenschonend; empfohlen für textzentrierte Crawler.
  - `metadata`: Liest (falls verfügbar) Metadaten mit `ffprobe` aus und liefert diese als JSON im Markdown. Erfordert installierte `ffprobe` (Teil von `ffmpeg`). Keine eigentliche Transkodierung.
  - `full`: Versucht volle Konvertierung via `markitdown`/`ffmpeg`. Diese Option kann langsam und ressourcenintensiv sein. Nur aktivieren, wenn AV‑Inhalte tatsächlich benötigt werden.
  - `none`: keinerlei Markdown‑Ausgabe für Medien – wahrhaft „stumm schalten“.

Hinweise:
- Bei `skip` werden laute Warnungen von `pydub/ffmpeg` unterdrückt.
- Für `metadata`/`full` sollte `ffprobe/ffmpeg` installiert und im PATH verfügbar sein.

#### Converter‑Hinweise

- Circuit Breaker (automatisch): Bei mehreren unerwarteten MarkItDown‑Fehlern in kurzer Zeit wird MarkItDown prozessweit automatisch deaktiviert und wieder auf Fallback umgeschaltet. Erwartete Konvertierungsfehler (z. B. kaputte PDFs) triggern den Breaker nicht.

#### Sicherheit (NEU)

- `ALLOW_INSECURE_SSL` (Standard: `false`)
  - Wenn `true`, werden TLS‑Zertifikate nicht validiert (`verify=False` in httpx). Das kann abgelaufene/fehlerhafte Zertifikate umgehen, ist aber aus Sicherheitsgründen nicht empfohlen. Nur für Tests verwenden.

Antwort (Beispiel):

```json
{
  "request_mode": "fast",
  "requested_url": "https://example.com",
  "final_url": "https://www.example.com/",
  "status_code": 200,
  "redirected": true,
  "content_type": "text/html; charset=utf-8",
  "markdown": "# Example Domain\n...",
  "markdown_length": 1234,
  "error_page_detected": false,
  "links": [
    {
      "url": "https://www.iana.org/domains/example",
      "text": "Example",
      "internal": false,
      "category": "content"
    }
  ],
  "llm": null,
  "elapsed_ms": 456
}
```

## Hinweise

- Sessions werden pro Crawl geöffnet und sauber geschlossen (httpx-Client Kontexte, Selenium Driver-Pool). Das kostet etwas Speed, erhöht aber Robustheit.
- `markitdown` arbeitet über eine temporäre Datei mit passender Endung (abgeleitet aus MIME-Type). So werden alle unterstützten Formate zuverlässig erkannt.
- Anti-Bot/Cloudflare-Umgehung ist best effort – harte Schutzmechanismen können u.U. nicht zuverlässig umgangen werden.
- Für LLM-Nachbearbeitung muss `LLM_API_KEY` oder `OPENAI_API_KEY` in `.env` gesetzt sein (oder als Systemumgebungsvariable für Google Colab). Standard: Base URL `https://api.openai.com/v1`, Modell `gpt-5-mini`.

## Architektur

**JS-Modus (Selenium):** Verwendet einen intelligenten Driver-Pool-Ansatz:
- **Dynamische Pool-Skalierung**: Startet mit `SELENIUM_POOL_SIZE` (Standard: 2), skaliert automatisch bis `SELENIUM_MAX_POOL_SIZE` (Standard: 8) bei hoher Last
- **Intelligente Warteschlange**: Überschüssige Requests werden in einer Queue gehalten (bis zu `MAX_QUEUE_SIZE`), statt sofort abgelehnt zu werden
- **Kapazitätsmanagement**: Bis zu `MAX_CONCURRENT_REQUESTS` gleichzeitige Verarbeitungen möglich
- **Health Checks**: Defekte Driver werden automatisch erkannt und ersetzt
- **Monitoring**: `/stats` Endpoint zeigt aktuelle Pool-Größen und Auslastung
- Stealth-Features: headless, Anti-Automation-Detection, Cookie-Banner-Klick
- Automatische Chrome WebDriver-Installation über webdriver-manager

**Fast-Modus (httpx):** Direkter asynchroner HTTP-Client im Hauptprozess.

### JS‑Modus Pipeline (Selenium)

1) WebDriver & Stealth
   - Headless Chrome mit stabilitätsfördernden Flags, feste Viewport‑Größe (1920×1080)
   - Anti‑Automation: `--disable-blink-features=AutomationControlled`, `excludeSwitches=["enable-automation"]`
   - Stealth‑Script defensiv: setzt nur konfigurierbare Properties, keine harte Neudefinition von `window.chrome`; Guards für `navigator.webdriver`, `plugins`, `languages`, `permissions.query` (alles try/catch)

2) Navigation & Cookie‑Banner
   - Seitenaufruf mit Timeout/Retry
   - Cookie‑Banner: heuristische Selektoren, Scroll‑into‑view und JS‑Click‑Fallback

3) Optimierte Extraktion (Vereinfacht)
   - **Speed-Modus**: 1s Settle-Zeit + direkte Extraktion (sehr schnell, ~2-6s)
   - **Accuracy-Modus**: 2s Settle-Zeit + direkte Extraktion (ausgewogen, ~8-12s)
   - Keine komplexe SPA-Pipeline mehr - universeller Ansatz für alle Seitentypen
   - Besonders optimiert für Bildungsseiten (KMap, LEIFI, BCCampus)

Fallback‑Strategie:
- Wenn der `speed`‑Modus trotz Retries mit Renderer‑Timeout/WebDriver‑Fehlern scheitert, wird einmalig ein kurzer `accuracy`‑Versuch innerhalb des verbleibenden Zeitbudgets durchgeführt (kein permanenter Moduswechsel). So erhöhen wir die Erfolgsquote bei problematischen Seiten, ohne die allgemeine Performance zu verschlechtern.

4) Extraktion & Konvertierung
   - HTML → Markdown via MarkItDown
   - Vorreinigung von HTML: `<noscript>` entfernen, kleine „Enable JavaScript"‑Banner (DE/EN) entfernen, um False‑Positives zu vermeiden
   - Optional: Link‑Extraktion und Klassifizierung

### Fehlerseitenerkennung (Semantik)

- `utils.detect_error_page(text, status_code)` setzt `error_page_detected=true`, wenn
  - HTTP‑Status ≥ 400, oder
  - im Text typische Hinweise vorkommen (z. B. „not found“, „forbidden“, „captcha“, „cloudflare“, deutsche Varianten)
- Hinweis: Manche Seiten liefern Fehlerinhalte mit HTTP 200 (gebrandete 404). In diesem Fall bleibt `status_code=200`, aber `error_page_detected` kann `true` sein. Die API schlägt dann nicht fehl; das Flag dient der Transparenz.

### Tipps für den JS‑Modus

- Bei hartem Bot‑Schutz ggf. Proxy setzen (`proxy` oder `.env`) und Timeout erhöhen
- **Pool-Konfiguration**: Starte konservativ (`SELENIUM_POOL_SIZE=2`, `SELENIUM_MAX_POOL_SIZE=6`) und erhöhe basierend auf Monitoring
- **Kapazitäts-Monitoring**: Nutze `/stats` Endpoint zur Überwachung der Pool-Auslastung
- **Queue-Tuning**: Bei häufigen 503-Fehlern `MAX_QUEUE_SIZE` oder `QUEUE_TIMEOUT_SECONDS` erhöhen
- `DEFAULT_USER_AGENT` in `.env` anpassen, falls nötig

### Neue API-Endpoints

**GET `/stats`** - Kapazitäts-Monitoring

Zeigt aktuelle Systemauslastung und Pool-Status:

```json
{
  "concurrent_requests": 4,
  "max_concurrent": 8,
  "queue_size": 12,
  "max_queue_size": 50,
  "selenium_pools": {
    "normal": {
      "size": 6,
      "usage": 4,
      "available": 2
    },
    "eager": {
      "size": 4,
      "usage": 2,
      "available": 2
    }
  }
}
```

### Aktuelle Optimierungen (Performance)

- **SPA-Pipeline entfernt**: Komplexe SPA-Erkennung und -Wartezeiten eliminiert für drastische Performance-Verbesserung
- **Universelle Settle-Zeiten**: Speed-Modus (1s) und Accuracy-Modus (2s) mit direkter Extraktion
- **Bildungsseiten-optimiert**: Besonders für KMap, LEIFI, BCCampus (von 108s auf ~8-12s reduziert)
- **Stealth-Features**: Anti-Automation-Detection, realistische Browser-Profile
- **Cookie-Banner-Handling**: Automatisches Erkennen und Wegklicken
- **HTML-Vorreinigung**: Entfernt `<noscript>` und „Enable JavaScript"-Banner vor Markdown-Konvertierung
- **Fehlerseitenerkennung**: Transparente Kennzeichnung auch bei HTTP 200 mit Fehlerinhalt

## Troubleshooting

- **JS-Modus funktioniert nicht:**
  - Chrome WebDriver wird automatisch installiert beim ersten Start
  - Bei Problemen: Antivirus/Firewall prüfen (Chrome-Prozesse können blockiert werden)
  - Pool-Größe kann in `.env` angepasst werden (SELENIUM_POOL_SIZE=2)

- **Kapazitätsprobleme:**
  - **503 Service Unavailable**: Server überlastet, Queue voll → `MAX_QUEUE_SIZE` erhöhen oder später versuchen
  - **504 Gateway Timeout**: Request zu lange in Queue → `QUEUE_TIMEOUT_SECONDS` erhöhen
  - **Hohe Latenz**: Pool zu klein für Last → `SELENIUM_MAX_POOL_SIZE` erhöhen
  - **Monitoring**: `/stats` Endpoint regelmäßig prüfen für Optimierung

- **Performance-Optimierung:**
  - **Niedrige Auslastung**: `SELENIUM_POOL_SIZE` reduzieren (spart Ressourcen)
  - **Hohe Burst-Last**: `MAX_QUEUE_SIZE` und `QUEUE_TIMEOUT_SECONDS` erhöhen
  - **Konstant hohe Last**: `SELENIUM_MAX_POOL_SIZE` erhöhen
  
