"""Manejo de errores y registro (logging) del pipeline."""
from __future__ import annotations

import datetime as _dt
import logging
import traceback
from pathlib import Path


class PDFConversionError(Exception):
    """Error recuperable durante la conversión de un PDF concreto."""


class OCRUnavailableError(PDFConversionError):
    """Tesseract / pytesseract / Pillow no están disponibles."""


def get_logger(verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("pdf2md")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    return logger


def record_failure(errors_dir: Path, pdf_path: Path, exc: Exception) -> Path:
    """Guarda el detalle de un fallo y lo añade al índice de problemas.

    Debe llamarse dentro de un bloque ``except`` para capturar el traceback.
    Devuelve la ruta del log individual creado.
    """
    errors_dir.mkdir(parents=True, exist_ok=True)
    now = _dt.datetime.now()
    detail = errors_dir / f"{pdf_path.stem}_{now:%Y%m%d_%H%M%S}.log"
    detail.write_text(
        f"Archivo: {pdf_path}\n"
        f"Fecha:   {now.isoformat(timespec='seconds')}\n"
        f"Error:   {exc.__class__.__name__}: {exc}\n\n"
        f"{traceback.format_exc()}\n",
        encoding="utf-8",
    )
    index = errors_dir / "documentos_con_problemas.txt"
    with index.open("a", encoding="utf-8") as fh:
        fh.write(f"{now.isoformat(timespec='seconds')}\t{pdf_path.name}\t"
                 f"{exc.__class__.__name__}: {exc}\n")
    return detail
