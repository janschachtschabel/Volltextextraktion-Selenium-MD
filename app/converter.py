from __future__ import annotations

import os
import re
import tempfile
from typing import Optional
from markitdown import MarkItDown
from bs4 import BeautifulSoup
from .utils import guess_extension


def preserve_mathematical_content(text: str) -> str:
    """Preserve and enhance mathematical symbols and formulas in text."""
    # Common mathematical symbol mappings for better preservation
    math_replacements = {
        # Greek letters
        'α': 'α', 'β': 'β', 'γ': 'γ', 'δ': 'δ', 'ε': 'ε', 'ζ': 'ζ', 'η': 'η', 'θ': 'θ',
        'ι': 'ι', 'κ': 'κ', 'λ': 'λ', 'μ': 'μ', 'ν': 'ν', 'ξ': 'ξ', 'ο': 'ο', 'π': 'π',
        'ρ': 'ρ', 'σ': 'σ', 'τ': 'τ', 'υ': 'υ', 'φ': 'φ', 'χ': 'χ', 'ψ': 'ψ', 'ω': 'ω',
        
        # Mathematical operators
        '∑': '∑', '∏': '∏', '∫': '∫', '∮': '∮', '∂': '∂', '∇': '∇',
        '√': '√', '∛': '∛', '∜': '∜',
        '±': '±', '∓': '∓', '×': '×', '÷': '÷', '⋅': '⋅',
        '≤': '≤', '≥': '≥', '≠': '≠', '≈': '≈', '≡': '≡', '∝': '∝',
        '∞': '∞', '∅': '∅', '∈': '∈', '∉': '∉', '⊂': '⊂', '⊃': '⊃',
        
        # Superscripts and subscripts
        '²': '²', '³': '³', '¹': '¹', '⁰': '⁰', '⁴': '⁴', '⁵': '⁵',
        '⁶': '⁶', '⁷': '⁷', '⁸': '⁸', '⁹': '⁹',
        '₀': '₀', '₁': '₁', '₂': '₂', '₃': '₃', '₄': '₄', '₅': '₅',
        '₆': '₆', '₇': '₇', '₈': '₈', '₉': '₉',
        
        # Units and measurements
        '°': '°', '′': '′', '″': '″', '‰': '‰', '‱': '‱',
        'µ': 'µ', 'Ω': 'Ω', 'Å': 'Å',
    }
    
    # Apply mathematical symbol preservation
    for symbol, replacement in math_replacements.items():
        text = text.replace(symbol, replacement)
    
    # Preserve mathematical expressions in parentheses
    math_expr_pattern = r'\b([a-zA-Z]\([^)]*\)|[a-zA-Z][₀-₉⁰-⁹]*\s*[=+\-*/]\s*[^\s]+)'
    text = re.sub(math_expr_pattern, r'`\1`', text)
    
    # Preserve formulas with equals signs
    formula_pattern = r'([a-zA-Z][₀-₉⁰-⁹]*\s*=\s*[^\n]+)'
    text = re.sub(formula_pattern, r'**\1**', text)
    
    return text


def enhance_table_structure(text: str) -> str:
    """Enhance table structure preservation in markdown."""
    lines = text.split('\n')
    enhanced_lines = []
    in_table = False
    
    for line in lines:
        # Detect potential table rows (multiple | characters)
        if '|' in line and line.count('|') >= 2:
            if not in_table:
                # Starting a new table - add header separator if missing
                in_table = True
                enhanced_lines.append(line)
                # Check if next line is separator, if not add one
                if len(enhanced_lines) > 0:
                    cells = line.split('|')
                    separator = '|' + '|'.join(['---' for _ in range(len(cells)-1)]) + '|'
                    enhanced_lines.append(separator)
            else:
                enhanced_lines.append(line)
        else:
            if in_table:
                # End of table
                in_table = False
                enhanced_lines.append('')  # Add blank line after table
            enhanced_lines.append(line)
    
    return '\n'.join(enhanced_lines)


def bytes_to_markdown(data: bytes, content_type: Optional[str], url: Optional[str] = None) -> str:
    """
    Convert arbitrary bytes to Markdown using markitdown[all] with enhanced mathematical and table preservation.
    Strategy: write to a temp file with an appropriate extension based on MIME type.
    """
    ext = guess_extension(content_type)
    # If we have HTML but content looks binary or empty, still attempt
    fd, path = tempfile.mkstemp(suffix=ext)
    try:
        # Optional pre-cleaning for HTML to remove noscript/JS-required banners
        to_write = data
        if ext == ".html":
            try:
                html_text = data.decode("utf-8", errors="ignore")
                soup = BeautifulSoup(html_text, "lxml")
                # Remove all <noscript> blocks
                for tag in soup.find_all("noscript"):
                    tag.decompose()
                # Remove common JS-required banners by id/class hints
                hints = ["noscript", "no-js", "js-disabled", "enable-js", "javascript"]
                for el in soup.find_all(True):
                    attr_text = " ".join(
                        [str(el.get("id", "")), " ".join(el.get("class", []))]
                    ).lower()
                    if any(h in attr_text for h in hints):
                        # If the element is short text or clearly a banner, drop it
                        txt = (el.get_text(strip=True) or "")
                        if len(txt) <= 200:
                            el.decompose()
                # Remove short texts that explicitly ask to enable JS (DE/EN)
                js_msgs = re.compile(
                    r"(enable\s+javascript|javascript\s+required|please\s+enable\s+javascript|"
                    r"bitte.*javascript.*(aktivieren|einschalten)|javascript\s+wird\s+ben(ö|o)tigt)",
                    re.IGNORECASE,
                )
                for t in soup.find_all(string=js_msgs):
                    parent = t.parent
                    # Only remove if small and likely a banner
                    if parent and len((parent.get_text(strip=True) or "")) <= 200:
                        parent.decompose()
                cleaned = str(soup)
                to_write = cleaned.encode("utf-8", errors="ignore")
            except Exception:
                to_write = data

        with os.fdopen(fd, "wb") as f:
            f.write(to_write)
        md = MarkItDown()
        result = md.convert(path)
        # markitdown returns an object with .text_content
        text = getattr(result, "text_content", None)
        if isinstance(text, str) and text.strip():
            # Apply mathematical content preservation
            text = preserve_mathematical_content(text)
            # Enhance table structure
            text = enhance_table_structure(text)
            return text
        # Fallback to any string representation
        if isinstance(result, str):
            result = preserve_mathematical_content(result)
            result = enhance_table_structure(result)
            return result
        # As a last resort, return decoded text with enhancements
        try:
            decoded = data.decode("utf-8", errors="ignore")
            decoded = preserve_mathematical_content(decoded)
            return decoded
        except Exception:
            return ""
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
