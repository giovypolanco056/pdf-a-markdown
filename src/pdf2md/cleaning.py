"""Limpieza y normalización del texto extraído / OCR.

Filosofía: limpiar SIN inventar. Se corrigen artefactos evidentes (ligaduras,
espacios raros, caracteres de control, cabeceras/pies repetidos) pero no se
"adivinan" palabras del OCR: eso se deja como aviso en la carpeta de errores.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

from .models import BlockType, DocumentResult, Page

_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}
_WS_RE = re.compile(r"[ \t ]+")


def _normalize_text(text: str) -> str:
    for k, v in _LIGATURES.items():
        text = text.replace(k, v)
    # quitar caracteres de control (categoría Unicode "C*"), conservando saltos
    text = "".join(ch for ch in text if ch == "\n" or unicodedata.category(ch)[0] != "C")
    return _WS_RE.sub(" ", text).strip()


def _non_empty(block) -> bool:
    if block.type == BlockType.LIST:
        return bool(block.items)
    if block.type == BlockType.TABLE:
        return bool(block.rows)
    return bool(block.text.strip())


def clean_document(doc: DocumentResult, remove_headers_footers: bool = True) -> None:
    """Limpia in-place todos los bloques del documento."""
    if remove_headers_footers and len(doc.pages) >= 3:
        _remove_running_headers_footers(doc.pages)

    for page in doc.pages:
        for block in page.blocks:
            if block.type in (BlockType.HEADING, BlockType.PARAGRAPH):
                block.text = _normalize_text(block.text)
            elif block.type == BlockType.LIST:
                block.items = [_normalize_text(it) for it in block.items if it.strip()]
            elif block.type == BlockType.TABLE:
                block.rows = [[_normalize_text(c) for c in row] for row in block.rows]
        page.blocks = [b for b in page.blocks if _non_empty(b)]


def _remove_running_headers_footers(pages: list[Page]) -> None:
    """Elimina líneas que se repiten como cabecera/pie en la mayoría de páginas."""
    tops: Counter = Counter()
    bottoms: Counter = Counter()
    for p in pages:
        tb = [b for b in p.blocks if b.type in (BlockType.HEADING, BlockType.PARAGRAPH)]
        if tb:
            tops[tb[0].text.strip()] += 1
            bottoms[tb[-1].text.strip()] += 1

    threshold = max(2, int(len(pages) * 0.6))
    repeated = {t for t, c in tops.items() if c >= threshold and 0 < len(t) <= 80}
    repeated |= {b for b, c in bottoms.items() if c >= threshold and 0 < len(b) <= 80}
    if not repeated:
        return

    for p in pages:
        p.blocks = [
            b for b in p.blocks
            if not (b.type in (BlockType.HEADING, BlockType.PARAGRAPH)
                    and b.text.strip() in repeated)
        ]
