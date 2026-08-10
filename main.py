#!/usr/bin/env python3
"""Conversor PDF -> Markdown (Fase 1 del sistema RAG).

Ejemplos de uso:
    python main.py                          # documentos/originales -> documentos/markdown
    python main.py -i mi_archivo.pdf
    python main.py -i entrada -o salida --recursive --overwrite
    python main.py --tesseract "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite ejecutar "python main.py" sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pdf2md.config import Config          # noqa: E402
from pdf2md.pipeline import convert_path  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convierte PDFs (digitales o escaneados) a Markdown estructurado.")
    p.add_argument("-i", "--input", help="PDF o carpeta de entrada")
    p.add_argument("-o", "--output", help="Carpeta de salida para los .md")
    p.add_argument("-c", "--config", default="config.yaml", help="Ruta a config.yaml")
    p.add_argument("--lang", help="Idioma para los metadatos (p. ej. es)")
    p.add_argument("--ocr-lang", help="Idioma de Tesseract (p. ej. spa, spa+eng)")
    p.add_argument("--dpi", type=int, help="Resolución de render para OCR (p. ej. 300)")
    p.add_argument("--tesseract", help="Ruta al ejecutable de Tesseract")
    p.add_argument("--tessdata-dir", help="Carpeta con los .traineddata")
    p.add_argument("--recursive", action="store_true", help="Buscar PDFs en subcarpetas")
    p.add_argument("--overwrite", action="store_true", help="Sobrescribir .md existentes")
    p.add_argument("--no-tables", action="store_true", help="Desactivar detección de tablas")
    p.add_argument("--no-page-markers", action="store_true", help="No insertar marcas de página")
    p.add_argument("-v", "--verbose", action="store_true", help="Salida detallada")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    config = Config.load(args.config)

    if args.lang:
        config.language = args.lang
    if args.ocr_lang:
        config.ocr_lang = args.ocr_lang
    if args.dpi:
        config.ocr_dpi = args.dpi
    if args.tesseract:
        config.tesseract_cmd = args.tesseract
    if args.tessdata_dir:
        config.tessdata_dir = args.tessdata_dir
    if args.recursive:
        config.recursive = True
    if args.overwrite:
        config.overwrite = True
    if args.no_tables:
        config.detect_tables = False
    if args.no_page_markers:
        config.include_page_markers = False

    summary = convert_path(config, args.input, args.output, args.verbose)

    if summary["total"] == 0:
        print("No se procesó ningún PDF. Coloca archivos en 'documentos/originales' "
              "o indica una ruta con -i.")
    else:
        print(f"\nResumen: {summary['ok']} OK · {summary['skipped']} omitidos · "
              f"{summary['failed']} con error (de {summary['total']} PDF).")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
