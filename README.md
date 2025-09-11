# Volltextextraktion Selenium MD

Ein schlankes FastAPI-Projekt zum asynchronen Crawlen von Webseiten und automatischen Umwandeln in Markdown mit `markitdown[all]`. Optional mit LLM-Nachbearbeitung (OpenAI, GPT-4.1-mini).

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
  "js_strategy": "speed",
  "mode": "auto",
  "timeout_ms": 180000,
  "retries": 2,
  "proxy": null,
  "max_bytes": 10485760,
  "extract_links": true,
  "llm_postprocess": false,
  "llm_clean_prompt": false,
  "llm_anonymize": false
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

**Voraussetzung**: `LLM_API_KEY` in `.env` konfiguriert

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
- `DEFAULT_TIMEOUT_SECONDS`: Standard-Timeout
- `DEFAULT_RETRIES`: Standard-Wiederholungen
- `DEFAULT_MAX_BYTES`: Standard-Dateigröße-Limit
- `DEFAULT_USER_AGENT`: Browser User-Agent für Selenium
- `DEFAULT_JS_AUTO_WAIT`: Automatische Wartezeiten im JS-Modus
- `DEFAULT_JS_STRATEGY`: Voreinstellung für die JS‑Strategie (`accuracy|speed`)
- `SELENIUM_POOL_SIZE`: Anzahl Chrome-Driver im Pool

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
- Für LLM-Nachbearbeitung muss `LLM_API_KEY` in `.env` gesetzt sein. Standard: Base URL `https://api.openai.com/v1`, Modell `gpt-4.1-mini`.

## Architektur

**JS-Modus (Selenium):** Verwendet einen Driver-Pool-Ansatz:
- Chrome-Driver werden beim Start initialisiert und in einem Pool gehalten (konfigurierbar via SELENIUM_POOL_SIZE)
- Jeder Request nimmt einen freien Driver aus dem Pool, nutzt ihn und gibt ihn zurück
- Natürliche Parallelitätsbegrenzung durch Pool-Größe (Standard: 2 gleichzeitige JS-Requests)
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
- `SELENIUM_POOL_SIZE` steuert Parallelität; zu hoch kann Instabilität verursachen
- `DEFAULT_USER_AGENT` in `.env` anpassen, falls nötig

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
