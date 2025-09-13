# ======================================================================================
# Korrigiertes Script für Google Colab - Volltextextraktion Selenium MD API
# Repository: https://github.com/janschachtschabel/Volltextextraktion-Selenium-MD
# ======================================================================================

# Umgebungsvariablen aus der .env Datei setzen und Openai API Key aus Colab Secrets ziehen

import os
from google.colab import userdata
import subprocess
import sys
import re
import threading
import time
import requests
from IPython.display import clear_output

# 1) Feste Defaults direkt setzen (alles außer dem Key)
os.environ.update({
    "PORT":"8000",
    "HOST":"0.0.0.0",
    "LLM_BASE_URL":"https://api.openai.com/v1",
    "LLM_MODEL":"gpt-5-mini",
    "DEFAULT_TIMEOUT_SECONDS":"120",
    "DEFAULT_RETRIES":"1",
    "DEFAULT_HEADLESS":"true",
    "DEFAULT_STEALTH":"true",
    "DEFAULT_JS_AUTO_WAIT":"true",
    "DEFAULT_MAX_BYTES":"10485760",
    "DEFAULT_USER_AGENT":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "SELENIUM_POOL_SIZE":"4",
    "DEFAULT_JS_STRATEGY":"speed",
})

# 2) Key sicher aus Colab Secrets ziehen (ohne Anzeige)
key = userdata.get("OPENAI_API_KEY")
if key:
    os.environ["OPENAI_API_KEY"] = key
else:
    # Optionaler Fallback ohne Anzeige:
    from getpass import getpass
    os.environ["OPENAI_API_KEY"] = getpass("OpenAI API key (wird nicht angezeigt): ")

# 3) Prüfen, ohne den Key zu leaken
print("OPENAI_API_KEY geladen:", bool(os.environ.get("OPENAI_API_KEY")))

# Git installieren
subprocess.run("sudo apt-get update && sudo apt-get install -y git", shell=True, check=True)

# Chrome installieren (für Selenium)
subprocess.run("wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -", shell=True, check=True)
subprocess.run("sudo sh -c 'echo \"deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main\" >> /etc/apt/sources.list.d/google-chrome.list'", shell=True, check=True)
subprocess.run("sudo apt-get update", shell=True, check=True)
subprocess.run("sudo apt-get install -y google-chrome-stable", shell=True, check=True)

# Cloudflare Tunnel installieren
subprocess.run("wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb", shell=True, check=True)
subprocess.run("sudo dpkg -i cloudflared-linux-amd64.deb", shell=True, check=True)

# KORRIGIERTE Repository URL und Pfad
subprocess.run("git clone https://github.com/janschachtschabel/Volltextextraktion-Selenium-MD.git /content/Volltextextraktion-Selenium-MD", shell=True, check=True)
os.chdir('/content/Volltextextraktion-Selenium-MD')

# Dependencies installieren
subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

# Chrome-Konfiguration für Google Colab patchen (Python-basiert)
import os
import sys
sys.path.insert(0, '/content/Volltextextraktion-Selenium-MD')

# Chrome-Patch direkt als Python-Code definieren
chrome_patch_code = '''
import os
import sys
sys.path.insert(0, '/content/Volltextextraktion-Selenium-MD')

def patch_js_fetcher():
    try:
        from app import js_fetcher
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        
        def colab_create_driver(proxy=None, user_agent=None, page_load_strategy='normal'):
            options = Options()
            options.binary_location = "/usr/bin/google-chrome"
            options.add_argument("--headless=new")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Alle anderen Optionen aus dem Original übernehmen
            options.add_argument("--disable-logging")
            options.add_argument("--log-level=3")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--disable-features=TranslateUI,BlinkGenPropertyTrees,VizDisplayCompositor")
            options.add_argument("--disable-ipc-flooding-protection")
            options.add_argument("--disable-default-apps")
            options.add_argument("--disable-sync")
            options.add_argument("--disable-background-networking")
            options.add_argument("--remote-debugging-port=0")
            options.add_argument("--disable-web-security")
            options.add_argument("--disable-hang-monitor")
            options.add_argument("--disable-prompt-on-repost")
            options.add_argument("--disable-domain-reliability")
            options.add_argument("--disable-component-extensions-with-background-pages")
            options.add_argument("--disable-client-side-phishing-detection")
            options.add_argument("--disable-popup-blocking")
            options.add_argument("--disable-translate")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-permissions-api")
            options.add_argument("--memory-pressure-off")
            options.add_argument("--max_old_space_size=4096")
            options.add_argument("--aggressive-cache-discard")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--start-maximized")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins-discovery")
            options.add_argument("--disable-plugins")
            options.add_argument("--disable-images")
            options.add_argument("--disable-javascript-harmony-shipping")
            
            if user_agent:
                options.add_argument(f"--user-agent={user_agent}")
            else:
                options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            if proxy and proxy.strip() and proxy.strip().lower() != "string":
                options.add_argument(f"--proxy-server={proxy}")
                options.add_argument("--ignore-ssl-errors-on-proxy")
                options.add_argument("--ignore-certificate-errors-spki-list")
                options.add_argument("--ignore-certificate-errors")
            
            try:
                if page_load_strategy in ('eager', 'normal'):
                    options.page_load_strategy = page_load_strategy
            except Exception:
                pass
            
            # ChromeDriver Service - verwende System-Installation
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            
            from selenium import webdriver
            driver = webdriver.Chrome(service=service, options=options)
            
            try:
                setattr(driver, "_strategy_key", 'eager' if page_load_strategy == 'eager' else 'normal')
            except Exception:
                pass
            
            # Stealth script ausführen (vereinfacht für Colab)
            try:
                driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                """)
            except:
                pass
            
            return driver
        
        # Patch anwenden
        js_fetcher._create_driver = colab_create_driver
        print("✅ Chrome-Konfiguration für Google Colab gepatcht")
        
    except Exception as e:
        print(f"⚠️ Chrome-Patch Fehler: {e}")

patch_js_fetcher()
'''

# Chrome-Patch-Datei schreiben
with open('/content/Volltextextraktion-Selenium-MD/colab_chrome_patch.py', 'w') as f:
    f.write(chrome_patch_code)

# =============================================================================
# ENVIRONMENT CONFIGURATION - KORRIGIERT
# =============================================================================

# Korrigierte Environment-Variablen für Volltextextraktion-Selenium-MD
os.environ["PYTHONPATH"] = "/content/Volltextextraktion-Selenium-MD"

# Chrome Binary Pfad für Google Colab
os.environ["CHROME_BIN"] = "/usr/bin/google-chrome"
os.environ["CHROMEDRIVER_PATH"] = "/usr/bin/chromedriver"

# Selenium Konfiguration für Google Colab
os.environ["GOOGLE_COLAB"] = "true"  # Flag für Colab-spezifische Anpassungen

# Optional: Logging configuration
os.environ["LOG_LEVEL"] = "INFO"

# Working directory setzen
os.chdir("/content/Volltextextraktion-Selenium-MD")

# =============================================================================
# HEALTH CHECK FUNCTIONS - KORRIGIERT
# =============================================================================

def check_fastapi_health(port=8000, max_attempts=30):
    """Prüft, ob FastAPI erfolgreich gestartet ist"""
    for attempt in range(max_attempts):
        try:
            # KORRIGIERTER Health-Check - verwendet root endpoint
            response = requests.get(f"http://localhost:{port}/", timeout=2)
            if response.status_code == 200:
                print(f"✅ Volltextextraktion-Selenium-MD API ist bereit! (Versuch {attempt + 1})")
                return True
        except requests.exceptions.RequestException:
            pass

        print(f"⏳ Warte auf Volltextextraktion-Selenium-MD API... (Versuch {attempt + 1}/{max_attempts})")
        time.sleep(2)

    return False

def run_fastapi_verbose():
    """Startet Volltextextraktion-Selenium-MD API mit ausführlicher Ausgabe"""
    print("🚀 Starte Volltextextraktion-Selenium-MD API mit detaillierter Ausgabe...")

    # Sicherstellen, dass wir im richtigen Verzeichnis sind
    os.chdir("/content/Volltextextraktion-Selenium-MD")

    # Chrome-Patch vor dem Start anwenden
    try:
        exec(open('/content/Volltextextraktion-Selenium-MD/colab_chrome_patch.py').read())
    except Exception as e:
        print(f"⚠️ Chrome-Patch konnte nicht angewendet werden: {e}")

    # KORRIGIERTER STARTBEFEHL für Volltextextraktion-Selenium-MD Repository
    process = subprocess.Popen(
        ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    # Ausgabe in Echtzeit anzeigen
    for line in process.stdout:
        print(line.strip())
        if "Uvicorn running on" in line or "Application startup complete" in line:
            print("✅ Volltextextraktion-Selenium-MD API erfolgreich gestartet!")
            break

def start_cloudflare_tunnel(port):
    """Startet Cloudflare Tunnel und extrahiert URL"""
    print(f"🌐 Starte Cloudflare Tunnel für Port {port}...")

    process = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    for line in process.stderr:
        print(f"Cloudflare: {line.strip()}")
        if "trycloudflare.com" in line:
            match = re.search(r'https?://[^\s]+', line)
            if match:
                return match.group(0)

    return None

# =============================================================================
# MAIN DEPLOYMENT SCRIPT
# =============================================================================

print("🚀 Volltextextraktion-Selenium-MD API - Google Colab Deployment")
print("📦 Repository: https://github.com/janschachtschabel/Volltextextraktion-Selenium-MD")
print("=" * 60)

# Schritt 1: FastAPI in separatem Thread starten
print("🔧 Starte Volltextextraktion-Selenium-MD API Server...")
fastapi_thread = threading.Thread(target=run_fastapi_verbose)
fastapi_thread.daemon = True
fastapi_thread.start()

# Schritt 2: Warten und Health Check
print("⏳ Warte auf API Bereitschaft...")
time.sleep(15)  # Längere Wartezeit für Selenium-Setup

if check_fastapi_health():
    print("✅ Volltextextraktion-Selenium-MD API läuft erfolgreich!")

    # Schritt 3: Cloudflare Tunnel starten
    tunnel_url = start_cloudflare_tunnel(8000)

    if tunnel_url:
        print(f"\n🎉 SUCCESS! Volltextextraktion-Selenium-MD API ist verfügbar unter:")
        print(f"🌐 Public URL: {tunnel_url}")
        print(f"📚 API Docs: {tunnel_url}/docs")
        print(f"🔍 ReDoc: {tunnel_url}/redoc")
        print(f"❤️ Health: {tunnel_url}/")
        print(f"🔗 Crawl Endpoint: {tunnel_url}/crawl")
        
        print(f"\n📋 Beispiel API-Aufruf:")
        print(f"""
curl -X POST "{tunnel_url}/crawl" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "url": "https://example.com",
    "mode": "auto",
    "js_strategy": "speed"
  }}'
        """)

    else:
        print("❌ Cloudflare Tunnel konnte nicht gestartet werden")

else:
    print("❌ Volltextextraktion-Selenium-MD API konnte nicht gestartet werden!")
    print("🔍 Debugging-Informationen:")

    # Directory-Check
    print("\n📁 Verzeichnis-Check:")
    subprocess.run(["ls", "-la", "/content/Volltextextraktion-Selenium-MD/"], check=False)

    print("\n📁 App Module Check:")
    subprocess.run(["ls", "-la", "/content/Volltextextraktion-Selenium-MD/app/"], check=False)

    # Dependencies-Check
    print("\n📦 Dependencies-Check:")
    subprocess.run('pip list | grep -E "(fastapi|uvicorn|selenium|markitdown)"', shell=True, check=False)

    # Manual start attempt
    print("\n🔧 Manueller Start-Versuch:")
    subprocess.run([sys.executable, "-c", "from app.main import app; print('✅ App import erfolgreich')"], check=False, cwd="/content/Volltextextraktion-Selenium-MD")

print("\n" + "=" * 60)
print("🏁 Deployment-Script beendet")
