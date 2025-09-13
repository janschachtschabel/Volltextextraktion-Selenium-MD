from __future__ import annotations

import json
import re
from typing import Optional
from openai import OpenAI, AsyncOpenAI


SYSTEM_PROMPT = (
    "Du bist ein Assistent, der Markdown-Texte bereinigt und klassifiziert. "
    "Reinige den Text, korrigiere Markdown-Strukturen, entferne offensichtliche Navigations-/Werbe-/Cookie-Hinweise. "
    "Arbeite nur den relevanten Artikel- oder Inhaltskern heraus. "
    "Klassifiziere das Ergebnis in genau eine der Kategorien: "
    "'Bildungsinhalt' (Markdown des Bildungsinhalts selbst), "
    "'Metabeschreibung' (beschreibende Infos über Bildungsinhalte, aber nicht der Inhalt selbst), "
    "'Fehler/Infoseite' (z.B. 404, Wartung, Zugriff verweigert). "
    "Gib ausschließlich JSON im folgenden Format zurück: {\n"
    "  \"cleaned_markdown\": string,\n"
    "  \"classification\": \"Bildungsinhalt|Metabeschreibung|Fehler/Infoseite\",\n"
    "  \"anonymized\": boolean\n"
    "}"
)


def _strip_code_fences(text: str) -> str:
    """Remove surrounding triple backtick code fences if present."""
    if not isinstance(text, str):
        return text
    # Match ```lang\n...``` or ```...```
    m = re.match(r"^```[a-zA-Z0-9_-]*\n([\s\S]*?)```\s*$", text.strip())
    if m:
        return m.group(1).strip()
    return text


def _extract_json_object(s: str) -> dict:
    """Best-effort extraction of a JSON object from arbitrary LLM text.

    - Strips code fences
    - Tries full-string json.loads
    - Falls back to extracting the first {...} that contains the key 'cleaned_markdown'
    """
    if not isinstance(s, str):
        return {}
    s1 = _strip_code_fences(s)
    # Try direct parse first
    try:
        return json.loads(s1)
    except Exception:
        pass
    # Try to locate a JSON object substring that includes the key of interest
    try:
        # Greedy to last closing brace
        # Prefer a block that contains the cleaned_markdown key
        for match in re.finditer(r"\{[\s\S]*?\}", s1):
            block = match.group(0)
            if '"cleaned_markdown"' in block:
                try:
                    return json.loads(block)
                except Exception:
                    continue
        # Fallback: last brace block
        last_open = s1.find('{')
        last_close = s1.rfind('}')
        if last_open != -1 and last_close != -1 and last_close > last_open:
            return json.loads(s1[last_open:last_close + 1])
    except Exception:
        pass
    return {}


def _flatten_cleaned_markdown(value: str) -> str:
    """Ensure cleaned_markdown is plain markdown, not code-fenced JSON or nested JSON.

    - Strip code fences
    - If the result looks like JSON and has a cleaned_markdown key, extract it
    - Finally, if still fenced (markdown fences), strip again
    """
    if not isinstance(value, str):
        return value
    text = _strip_code_fences(value)
    # If the text itself is JSON with cleaned_markdown, unwrap
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and 'cleaned_markdown' in obj:
            inner = obj.get('cleaned_markdown', '')
            return _strip_code_fences(inner or '')
    except Exception:
        pass
    return text


def postprocess_markdown(
    *,
    markdown: str,
    base_url: Optional[str],
    api_key: str,
    model: str,
    base: Optional[str] = None,
    clean_prompt: Optional[str] = None,
    anonymize: bool = False,
) -> tuple[str, str, bool, int | None]:
    """
    Returns: cleaned_markdown, classification, anonymized, tokens_used
    """
    client = OpenAI(api_key=api_key, base_url=base or None)

    user_prompt = """Bereinige folgenden Markdown-Inhalt. {extra}
---
{md}
---
""".format(
        extra=(clean_prompt or "").strip()
        + ("\nFühre zusätzlich eine Anonymisierung personenbezogener Daten durch." if anonymize else ""),
        md=markdown,
    )

    # Prefer Responses API if available; fallback to chat.completions
    try:
        # Responses API
        resp = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = resp.output_text  # type: ignore[attr-defined]
        usage = getattr(resp, "usage", None)
        tokens_used = getattr(usage, "total_tokens", None) if usage else None
    except Exception:
        # Fallback to Chat Completions
        chat = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = chat.choices[0].message.content if chat.choices else ""
        tokens_used = getattr(chat, "usage", None).total_tokens if getattr(chat, "usage", None) else None

    cleaned = markdown
    classification = "Metabeschreibung"
    anonymized = anonymize

    try:
        data = _extract_json_object(content or "")
        if data:
            new_cleaned = data.get("cleaned_markdown")
            if isinstance(new_cleaned, str):
                cleaned = _flatten_cleaned_markdown(new_cleaned) or cleaned
            classification = data.get("classification", classification) or classification
            anonymized = bool(data.get("anonymized", anonymized))
        else:
            raise ValueError("no_json")
    except Exception:
        # If not JSON, try to keep the content if looks like markdown
        if isinstance(content, str) and content.strip():
            cleaned = _strip_code_fences(content.strip())

    return cleaned, classification, anonymized, tokens_used


async def postprocess_markdown_async(
    *,
    markdown: str,
    base_url: Optional[str],
    api_key: str,
    model: str,
    base: Optional[str] = None,
    clean_prompt: Optional[str] = None,
    anonymize: bool = False,
) -> tuple[str, str, bool, int | None]:
    """
    Async variant to prevent blocking the event loop.
    Returns: cleaned_markdown, classification, anonymized, tokens_used
    """
    client = AsyncOpenAI(api_key=api_key, base_url=base or None)

    user_prompt = """Bereinige folgenden Markdown-Inhalt. {extra}
---
{md}
---
""".format(
        extra=(clean_prompt or "").strip()
        + ("\nFühre zusätzlich eine Anonymisierung personenbezogener Daten durch." if anonymize else ""),
        md=markdown,
    )

    # Prefer Responses API if available; fallback to chat.completions
    try:
        # Responses API
        resp = await client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = resp.output_text  # type: ignore[attr-defined]
        usage = getattr(resp, "usage", None)
        tokens_used = getattr(usage, "total_tokens", None) if usage else None
    except Exception:
        # Fallback to Chat Completions
        chat = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = chat.choices[0].message.content if chat.choices else ""
        tokens_used = getattr(chat, "usage", None).total_tokens if getattr(chat, "usage", None) else None

    cleaned = markdown
    classification = "Metabeschreibung"
    anonymized = anonymize

    try:
        data = _extract_json_object(content or "")
        if data:
            new_cleaned = data.get("cleaned_markdown")
            if isinstance(new_cleaned, str):
                cleaned = _flatten_cleaned_markdown(new_cleaned) or cleaned
            classification = data.get("classification", classification) or classification
            anonymized = bool(data.get("anonymized", anonymized))
        else:
            raise ValueError("no_json")
    except Exception:
        # If not JSON, try to keep the content if looks like markdown
        if isinstance(content, str) and content.strip():
            cleaned = _strip_code_fences(content.strip())

    return cleaned, classification, anonymized, tokens_used
