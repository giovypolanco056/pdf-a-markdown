"""Detección página a página: ¿texto digital o imagen escaneada?

Un mismo PDF puede ser mixto (portada escaneada + interior digital, por
ejemplo), por eso la decisión se toma por página y no para todo el documento.
"""
from __future__ import annotations


def alnum_count(text: str) -> int:
    return sum(1 for c in text if c.isalnum())


def classify_page(page, min_chars: int = 100) -> str:
    """Devuelve ``"text"`` si la página tiene texto extraíble, ``"ocr"`` si no.

    Heurística: si al extraer el texto con PyMuPDF hay suficientes caracteres
    alfanuméricos, la página es digital; si está prácticamente vacía, es una
    imagen escaneada y habrá que aplicarle OCR.
    """
    text = page.get_text("text")
    return "text" if alnum_count(text) >= min_chars else "ocr"
