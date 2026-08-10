"""Orquestador del pipeline PDF -> Markdown (conversión de uno o varios PDFs)."""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pymupdf as fitz  # PyMuPDF (import pymupdf evita el aviso de deprecación de "fitz")

from . import cleaning, ocr, text_extractor
from .config import Config
from .detector import classify_page
from .errors import OCRUnavailableError, PDFConversionError, get_logger, record_failure
from .markdown_writer import render_document
from .models import Block, BlockType, DocumentResult, Page

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **_kwargs):
        return iterable


# --------------------------------------------------------------------------- #
# Conversión de UN PDF
# --------------------------------------------------------------------------- #
def convert_pdf(pdf_path: Path, config: Config) -> DocumentResult:
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise PDFConversionError(f"No se pudo abrir el PDF: {exc}") from exc

    if doc.needs_pass and not doc.authenticate(""):
        doc.close()
        raise PDFConversionError("El PDF está cifrado y requiere contraseña.")

    result = DocumentResult(source_path=str(pdf_path))

    # 1) Clasificar cada página (digital vs. escaneada)
    kinds = [classify_page(doc[i], config.min_chars_text) for i in range(doc.page_count)]
    text_pages = [i for i, k in enumerate(kinds) if k == "text"]

    # 2) Modelo de fuentes del documento (para niveles de título consistentes)
    body_size, size_to_level = text_extractor.build_font_model(doc, text_pages)

    # 3) Preparar OCR sólo si hace falta
    ocr_ready = False
    if any(k == "ocr" for k in kinds):
        try:
            ocr.ensure_tesseract(config.tesseract_cmd, config.tessdata_dir, config.ocr_lang)
            ocr_ready = True
        except OCRUnavailableError as exc:
            result.warnings.append(str(exc))

    # 4) Procesar página a página
    for i in range(doc.page_count):
        page = Page(number=i + 1, source=kinds[i])
        if kinds[i] == "text":
            page.blocks = text_extractor.extract_page_blocks(
                doc[i], body_size, size_to_level, config.detect_tables)
        elif ocr_ready:
            page.blocks, page.ocr_confidence, warns = ocr.ocr_page(
                doc[i], config.ocr_lang, config.ocr_dpi, config.min_ocr_conf,
                config.tessdata_dir)
            page.warnings.extend(warns)
        else:
            page.blocks = [Block(type=BlockType.PARAGRAPH,
                                 text="> ⚠️ Página escaneada no procesada: OCR no disponible.")]
            page.warnings.append("OCR no disponible para esta página.")
        result.pages.append(page)

    # 5) Limpieza
    cleaning.clean_document(result, config.remove_headers_footers)

    # 6) Metadatos
    result.metadata = _build_metadata(doc, pdf_path, result, config)

    doc.close()
    return result


def _build_metadata(doc, pdf_path: Path, result: DocumentResult, config: Config) -> dict:
    pdf_meta = doc.metadata or {}

    title = (pdf_meta.get("title") or "").strip()
    if not title:   # si el PDF no trae título, usar el primer H1/H2 encontrado
        for page in result.pages:
            for b in page.blocks:
                if b.type == BlockType.HEADING:
                    title = b.text
                    break
            if title:
                break
    if not title:
        title = pdf_path.stem

    ocr_pages = [p for p in result.pages if p.source == "ocr"]
    confs = [p.ocr_confidence for p in ocr_pages if p.ocr_confidence is not None]

    meta = {
        "title": title,
        "source": pdf_path.name,
        "file_type": "pdf",
        "pages": len(result.pages),
        "ocr": bool(ocr_pages),
        "language": config.language,
        "date_processed": _dt.date.today().isoformat(),
    }
    author = (pdf_meta.get("author") or "").strip()
    if author:
        meta["author"] = author
    if ocr_pages:
        meta["ocr_pages"] = len(ocr_pages)
        if confs:
            meta["ocr_confidence"] = round(sum(confs) / len(confs), 1)
    meta["tags"] = []   # placeholder para clasificación futura (RAG / Obsidian)
    return meta


# --------------------------------------------------------------------------- #
# Procesamiento por LOTES
# --------------------------------------------------------------------------- #
def find_pdfs(input_path: Path, recursive: bool = False) -> list[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() == ".pdf" else []
    if not input_path.exists():
        return []
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(input_path.glob(pattern))


def convert_path(config: Config, input_override: str | None = None,
                 output_override: str | None = None, verbose: bool = False,
                 files=None, on_progress=None, should_cancel=None) -> dict:
    """Convierte un lote de PDFs.

    Parámetros opcionales pensados para la interfaz gráfica:
      * ``files``       -> lista explícita de PDFs (en vez de escanear una carpeta).
      * ``on_progress`` -> callback(done, total, nombre, estado, detalle) con
                           estado en {"start","ok","skip","error"}.
      * ``should_cancel`` -> callable() -> bool; si devuelve True, se detiene el lote.
    """
    logger = get_logger(verbose)
    output_dir = Path(output_override or config.output_dir)
    errors_dir = Path(config.errors_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if files is not None:
        pdfs = [Path(f) for f in files]
    else:
        input_path = Path(input_override or config.input_dir)
        pdfs = find_pdfs(input_path, config.recursive)

    total = len(pdfs)
    if not pdfs:
        logger.warning("No se encontraron PDFs.")
        return {"total": 0, "ok": 0, "failed": 0, "skipped": 0, "results": []}

    ok = failed = skipped = 0
    results: list[tuple[str, str]] = []
    for i, pdf_path in enumerate(tqdm(pdfs, desc="Convirtiendo", unit="pdf")):
        if should_cancel and should_cancel():
            logger.info("Cancelado por el usuario.")
            break
        if on_progress:
            on_progress(i, total, pdf_path.name, "start", "")

        out_file = output_dir / f"{pdf_path.stem}.md"
        if out_file.exists() and not config.overwrite:
            logger.info("Omitido (ya existe): %s", out_file.name)
            skipped += 1
            results.append((pdf_path.name, "skip"))
            if on_progress:
                on_progress(i + 1, total, pdf_path.name, "skip", "ya existe")
            continue
        try:
            result = convert_pdf(pdf_path, config)
            out_file.write_text(render_document(result, config.include_page_markers),
                                encoding="utf-8")
            warned = bool(result.warnings or any(p.warnings for p in result.pages))
            if warned:
                _write_warnings(errors_dir, pdf_path, result)
            logger.info("OK      %s -> %s", pdf_path.name, out_file.name)
            ok += 1
            results.append((pdf_path.name, "ok"))
            if on_progress:
                on_progress(i + 1, total, pdf_path.name, "ok",
                            "convertido con avisos" if warned else "convertido")
        except Exception as exc:   # continuar con el resto del lote pase lo que pase
            record_failure(errors_dir, pdf_path, exc)
            logger.error("FALLÓ   %s (%s: %s)", pdf_path.name, exc.__class__.__name__, exc)
            failed += 1
            results.append((pdf_path.name, "error"))
            if on_progress:
                on_progress(i + 1, total, pdf_path.name, "error",
                            f"{exc.__class__.__name__}: {exc}")

    logger.info("Terminado: %d OK, %d omitidos, %d con error (de %d).",
                ok, skipped, failed, total)
    return {"total": total, "ok": ok, "failed": failed, "skipped": skipped, "results": results}


def _write_warnings(errors_dir: Path, pdf_path: Path, result: DocumentResult) -> None:
    errors_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"Avisos para {pdf_path.name}:"]
    lines += [f"  - {w}" for w in result.warnings]
    for page in result.pages:
        lines += [f"  - [pág. {page.number}] {w}" for w in page.warnings]
    (errors_dir / f"{pdf_path.stem}_avisos.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
