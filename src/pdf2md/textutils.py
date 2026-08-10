"""Utilidades de texto compartidas por el extractor digital y el OCR."""
from __future__ import annotations

import re

# Viñetas y listas numeradas / con letra ("1.", "2)", "a.", "b)")
BULLET_RE = re.compile(r"^\s*([-*•·◦▪‣])\s+")
ORDERED_RE = re.compile(r"^\s*(\d{1,3}|[a-zA-Z])[.)]\s+")


def join_lines(lines: list[str]) -> str:
    """Une líneas resolviendo la separación silábica de fin de línea.

    Ejemplo: ["compañe-", "ros del equipo"] -> "compañeros del equipo".
    """
    out = ""
    for ln in lines:
        ln = ln.rstrip()
        if not out:
            out = ln
            continue
        if not ln:
            continue
        if out.endswith("-") and ln[:1].islower():
            out = out[:-1] + ln.lstrip()
        else:
            out = out + " " + ln.lstrip()
    return out.strip()


def is_list_line(text: str) -> bool:
    return bool(BULLET_RE.match(text) or ORDERED_RE.match(text))


def is_ordered(text: str) -> bool:
    return bool(ORDERED_RE.match(text))


def strip_list_marker(text: str) -> str:
    text = BULLET_RE.sub("", text)
    text = ORDERED_RE.sub("", text)
    return text.strip()
