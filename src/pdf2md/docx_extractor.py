"""Lector de Word (.docx) -> DocumentResult.

Produce los mismos ``Block`` que el lector de PDF, de modo que el resto del
pipeline (escritura de Markdown, metadatos, publicación a Obsidian) se reutiliza
sin cambios. Se apoya en ``python-docx``.

Mapeo:
  * párrafos con estilo "Heading N"/"Título N" -> encabezados (nivel N),
  * "Title"/"Subtitle" -> H1/H2,
  * párrafos de lista ("List Bullet"/"List Number"/"List Paragraph") -> listas,
  * tablas -> tablas Markdown,
  * el resto -> párrafos.
Word no tiene páginas reales en el archivo (la paginación es del visor), así que
todo el contenido va en una sola "página" lógica.
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

from .config import Config
from .errors import PDFConversionError
from .models import Block, BlockType, DocumentResult, Page

try:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph
except ImportError:  # pragma: no cover
    Document = None


def _require_docx() -> None:
    if Document is None:
        raise PDFConversionError(
            "Falta la librería 'python-docx'. Instálala con:  pip install python-docx")


def _iter_block_items(doc):
    """Genera los ``Paragraph`` y ``Table`` en el ORDEN real del documento.

    python-docx expone párrafos y tablas por separado y se pierde el orden; hay
    que recorrer el XML del cuerpo para intercalarlos correctamente.
    """
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def _heading_level(style_name: str) -> int | None:
    """Devuelve el nivel de encabezado (1-6) para un estilo, o None."""
    if not style_name:
        return None
    s = style_name.strip().lower()
    if s in ("title", "título", "titulo"):
        return 1
    if s in ("subtitle", "subtítulo", "subtitulo"):
        return 2
    m = re.match(r"(?:heading|título|titulo)\s*(\d+)", s)
    if m:
        return min(max(int(m.group(1)), 1), 6)
    return None


def _list_kind(paragraph) -> str | None:
    """Detecta si un párrafo es de lista. Devuelve "ordered"/"bullet"/None."""
    style = (paragraph.style.name if paragraph.style else "").lower()
    # Señal fuerte: numeración real en el XML (numPr).
    has_numpr = paragraph._p.find(qn("w:pPr")) is not None and \
        paragraph._p.pPr is not None and paragraph._p.pPr.numPr is not None
    if "number" in style or "número" in style or "numero" in style:
        return "ordered"
    if "bullet" in style or "viñeta" in style or "vineta" in style:
        return "bullet"
    if "list" in style or "lista" in style:
        return "bullet"
    if has_numpr:
        return "bullet"
    return None


def _table_rows(table) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table.rows:
        rows.append([_clean_cell(c.text) for c in row.cells])
    return rows


def _clean_cell(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()


def convert_docx(path: Path, config: Config) -> DocumentResult:
    _require_docx()
    path = Path(path)
    try:
        doc = Document(str(path))
    except Exception as exc:
        raise PDFConversionError(f"No se pudo abrir el Word: {exc}") from exc

    result = DocumentResult(source_path=str(path))
    page = Page(number=1, source="docx")
    blocks: list[Block] = []

    list_items: list[str] = []
    list_ordered = False

    def flush_list() -> None:
        nonlocal list_items, list_ordered
        if list_items:
            blocks.append(Block(type=BlockType.LIST, ordered=list_ordered,
                                items=list(list_items)))
            list_items = []

    for item in _iter_block_items(doc):
        if isinstance(item, Table):
            flush_list()
            rows = _table_rows(item)
            if any(any(cell for cell in r) for r in rows):
                blocks.append(Block(type=BlockType.TABLE, rows=rows))
            continue

        text = (item.text or "").strip()
        if not text:
            continue

        level = _heading_level(item.style.name if item.style else "")
        if level is not None:
            flush_list()
            blocks.append(Block(type=BlockType.HEADING, text=text, level=level))
            continue

        kind = _list_kind(item)
        if kind is not None:
            ordered = kind == "ordered"
            if list_items and ordered != list_ordered:
                flush_list()
            list_ordered = ordered
            list_items.append(text)
            continue

        flush_list()
        blocks.append(Block(type=BlockType.PARAGRAPH, text=text))

    flush_list()
    page.blocks = blocks
    result.pages.append(page)
    result.metadata = _build_metadata(doc, path, blocks, config)
    return result


def _build_metadata(doc, path: Path, blocks: list[Block], config: Config) -> dict:
    props = doc.core_properties
    title = (props.title or "").strip()
    if not title:
        for b in blocks:
            if b.type == BlockType.HEADING:
                title = b.text
                break
    if not title:
        title = path.stem

    words = sum(len(b.text.split()) for b in blocks if b.text)
    words += sum(len(" ".join(it).split()) for b in blocks for it in [b.items] if b.items)

    meta = {
        "title": title,
        "source": path.name,
        "file_type": "docx",
        "ocr": False,
        "language": config.language,
        "date_processed": _dt.date.today().isoformat(),
    }
    author = (props.author or "").strip()
    if author:
        meta["author"] = author
    if words:
        meta["words"] = words
    meta["tags"] = []
    return meta
