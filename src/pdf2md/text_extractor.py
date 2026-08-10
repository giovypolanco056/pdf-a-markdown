"""Extracción de texto ESTRUCTURADO de páginas digitales con PyMuPDF.

Estrategia para preservar la estructura:
  * Títulos/subtítulos -> se infieren del tamaño de fuente (y la negrita).
  * Listas             -> se detectan por el marcador inicial (-, •, 1., a)...).
  * Tablas             -> se detectan con `page.find_tables()` de PyMuPDF.
  * Párrafos           -> el resto del texto, uniendo líneas y de-hifenando.
El orden de lectura se conserva ordenando los bloques por su posición vertical.
"""
from __future__ import annotations

from collections import Counter

from . import textutils as tu
from .models import Block, BlockType

_BOLD_FLAG = 1 << 4  # bit 4 de span["flags"] = negrita


def build_font_model(doc, text_pages: list[int]) -> tuple[int, dict[int, int]]:
    """Analiza los tamaños de fuente de TODO el documento (páginas digitales).

    Devuelve ``(tamaño_del_cuerpo, {tamaño: nivel_de_titulo})``. Hacerlo a nivel
    de documento (y no de página) da niveles de título consistentes en todo el .md.
    """
    sizes: Counter = Counter()
    for pno in text_pages:
        for block in doc[pno].get_text("dict").get("blocks", []):
            if block.get("type", 0) != 0:      # 0 = bloque de texto
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = span.get("text", "").strip()
                    if txt:
                        sizes[round(span.get("size", 0))] += len(txt)
    if not sizes:
        return 12, {}
    body = sizes.most_common(1)[0][0]                       # tamaño más frecuente
    heading_sizes = sorted((s for s in sizes if s > body), reverse=True)
    size_to_level = {s: min(i + 1, 4) for i, s in enumerate(heading_sizes)}
    return body, size_to_level


def _line_info(line: dict) -> tuple[str, int, bool]:
    """Texto de una línea + su tamaño dominante + si es (mayoritariamente) negrita."""
    parts: list[str] = []
    sizes: Counter = Counter()
    bold_chars = total = 0
    for span in line.get("spans", []):
        t = span.get("text", "")
        parts.append(t)
        n = len(t.strip())
        if n:
            sizes[round(span.get("size", 0))] += n
            total += n
            if span.get("flags", 0) & _BOLD_FLAG:
                bold_chars += n
    size = sizes.most_common(1)[0][0] if sizes else 0
    is_bold = total > 0 and bold_chars / total > 0.6
    return "".join(parts), size, is_bold


def _looks_like_heading(text, size, body, is_bold, size_to_level) -> bool:
    if not text or len(text) > 120 or text.endswith((".", ",", ";", ":")):
        return False
    if size in size_to_level:
        return True
    return is_bold and size >= body and len(text) <= 60


def _clean_table(raw_rows) -> list[list[str]]:
    rows = []
    for row in raw_rows or []:
        cells = [(c or "").replace("\n", " ").strip() for c in row]
        if any(cells):
            rows.append(cells)
    return rows


def extract_page_blocks(page, body_size: int, size_to_level: dict,
                        detect_tables: bool = True) -> list[Block]:
    items: list[tuple[float, Block]] = []   # (posición_vertical, bloque)

    # 1) Tablas (y sus recuadros, para no duplicar su texto como párrafos)
    table_bboxes = []
    if detect_tables:
        try:
            for t in page.find_tables().tables:
                rows = _clean_table(t.extract())
                if rows:
                    items.append((t.bbox[1], Block(type=BlockType.TABLE, rows=rows)))
                    table_bboxes.append(t.bbox)
        except Exception:
            table_bboxes = []   # versiones antiguas de PyMuPDF o tablas problemáticas

    # 2) Texto (títulos, listas, párrafos)
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        bx0, by0, bx1, by1 = block.get("bbox", (0, 0, 0, 0))
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        if any(t[0] <= cx <= t[2] and t[1] <= cy <= t[3] for t in table_bboxes):
            continue   # ya representado como tabla

        infos = [_line_info(ln) for ln in block.get("lines", [])]
        texts = [i[0] for i in infos if i[0].strip()]
        if not texts:
            continue

        joined = tu.join_lines(texts)
        max_size = max((i[1] for i in infos), default=0)
        any_bold = any(i[2] for i in infos)

        # Título ANTES que lista: un título numerado ("1. Introducción") no debe
        # confundirse con una lista de un solo elemento.
        if len(texts) <= 2 and _looks_like_heading(joined, max_size, body_size,
                                                    any_bold, size_to_level):
            items.append((by0, Block(type=BlockType.HEADING, text=joined,
                                     level=size_to_level.get(max_size, 3))))
            continue

        if all(tu.is_list_line(t) for t in texts):
            items.append((by0, Block(
                type=BlockType.LIST,
                items=[tu.strip_list_marker(t) for t in texts],
                ordered=tu.is_ordered(texts[0]),
            )))
            continue

        items.append((by0, Block(type=BlockType.PARAGRAPH, text=joined)))

    items.sort(key=lambda it: it[0])
    return [b for _, b in items]
