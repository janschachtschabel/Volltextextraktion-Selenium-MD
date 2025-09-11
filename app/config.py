from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if not val:
        return default
    try:
        return int(val)
    except Exception:
        return default


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = _get_int("PORT", 8000)

    # LLM
    llm_base_url: str | None = os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1"
    llm_model: str | None = os.getenv("LLM_MODEL") or "gpt-4.1-mini"
    llm_api_key: str | None = os.getenv("LLM_API_KEY")

    # Crawl defaults
    default_timeout_seconds: int = _get_int("DEFAULT_TIMEOUT_SECONDS", 180)
    default_retries: int = _get_int("DEFAULT_RETRIES", 2)
    default_headless: bool = _get_bool("DEFAULT_HEADLESS", True)
    default_stealth: bool = _get_bool("DEFAULT_STEALTH", True)
    default_max_bytes: int = _get_int("DEFAULT_MAX_BYTES", 10 * 1024 * 1024)
    default_user_agent: str = os.getenv(
        "DEFAULT_USER_AGENT",
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36"
        ),
    )

    # Selenium settings
    selenium_pool_size: int = _get_int("SELENIUM_POOL_SIZE", 2)
    default_js_auto_wait: bool = _get_bool("DEFAULT_JS_AUTO_WAIT", True)
    # JS strategy: accuracy|speed
    default_js_strategy: str = os.getenv("DEFAULT_JS_STRATEGY", "speed")


settings = Settings()
