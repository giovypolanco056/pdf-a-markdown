"""Pruebas mínimas que NO requieren PDFs ni Tesseract.

Ejecutar con:  python -m pytest    (o simplemente:  python tests/test_smoke.py)
Comprueban la lógica pura: estructura -> Markdown y Markdown -> chunks (RAG).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pdf2md.markdown_writer import render_document
from pdf2md.models import Block, BlockType, DocumentResult, Page
from pdf2md.rag.interfaces import HeadingChunker


def _sample_document() -> DocumentResult:
    doc = DocumentResult(source_path="ejemplo.pdf")
    doc.metadata = {"title": "Documento de prueba", "source": "ejemplo.pdf",
                    "pages": 1, "ocr": False, "language": "es", "tags": []}
    doc.pages = [Page(number=1, blocks=[
        Block(type=BlockType.HEADING, text="Introducción", level=1),
        Block(type=BlockType.PARAGRAPH, text="Este es un párrafo de ejemplo."),
        Block(type=BlockType.HEADING, text="Datos", level=2),
        Block(type=BlockType.LIST, items=["Primero", "Segundo"], ordered=True),
        Block(type=BlockType.TABLE, rows=[["Nombre", "Edad"], ["Ana", "30"]]),
    ])]
    return doc


def test_render_markdown():
    md = render_document(_sample_document())
    assert md.startswith("---")
    assert "# Introducción" in md
    assert "## Datos" in md
    assert "1. Primero" in md
    assert "| Nombre | Edad |" in md
    assert "| --- | --- |" in md
    print("[OK] render_document produce Markdown válido")


def test_heading_chunker():
    md = render_document(_sample_document())
    chunks = HeadingChunker().chunk(md, source="ejemplo.pdf")
    assert chunks, "el chunker debería producir al menos un fragmento"
    assert any(c.heading_path and c.heading_path[0] == "Introducción" for c in chunks)
    assert all(c.page == 1 for c in chunks)
    print(f"[OK] HeadingChunker produjo {len(chunks)} fragmento(s) con procedencia")


if __name__ == "__main__":
    test_render_markdown()
    test_heading_chunker()
    print("\nTodas las pruebas de humo pasaron.")
