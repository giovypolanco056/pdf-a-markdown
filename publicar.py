#!/usr/bin/env python3
"""Publica los Markdown convertidos en una bóveda de Obsidian (Fase 2).

Una bóveda de Obsidian es sólo una carpeta con archivos .md. Este script toma
los .md de la carpeta de SALIDA del conversor y los copia a la bóveda, con el
front matter enriquecido (aliases + tags) y un índice navegable (Índice.md).

Ejecutar:  python publicar.py            (usa las rutas de config.yaml)
           o doble clic en  publicar.bat

>>> PARA CONFIGURAR <<<
    Edita config.yaml:  output_dir (origen de los .md) y  vault_dir (tu bóveda).
    O al ejecutar, pásalas directamente:
        python publicar.py -s "C:\\ruta\\md" -d "C:\\ruta\\MiBoveda"

Por defecto NO pisa notas que ya estén en la bóveda (para no perder lo que hayas
editado en Obsidian). Usa --overwrite para actualizarlas.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from pdf2md import vault              # noqa: E402
from pdf2md.config import Config      # noqa: E402
from pdf2md.errors import get_logger  # noqa: E402


def _abs(p) -> Path:
    p = Path(p)
    return p if p.is_absolute() else (PROJECT_DIR / p)


def main(argv=None) -> int:
    config = Config.load(str(PROJECT_DIR / "config.yaml"))

    ap = argparse.ArgumentParser(
        description="Publica los .md convertidos en una bóveda de Obsidian.")
    ap.add_argument("-s", "--source", help="Carpeta con los .md (por defecto: output_dir)")
    ap.add_argument("-d", "--vault", help="Carpeta raíz de la bóveda de Obsidian")
    ap.add_argument("--subdir", help="Subcarpeta dentro de la bóveda (\"\" para la raíz)")
    ap.add_argument("--tag", action="append",
                    help="Tag a añadir a cada nota (se puede repetir)")
    ap.add_argument("--no-index", action="store_true", help="No generar el índice")
    ap.add_argument("--overwrite", action="store_true",
                    help="Sobrescribir notas ya publicadas (pisa ediciones en Obsidian)")
    args = ap.parse_args(argv)

    logger = get_logger()

    vault_dir = args.vault or config.vault_dir
    if not vault_dir:
        logger.error('No hay bóveda configurada. Indica  --vault "C:\\ruta\\bóveda"  '
                     "o pon  vault_dir  en config.yaml.")
        return 2

    source = _abs(args.source or config.output_dir)
    if not source.exists():
        logger.error("La carpeta de origen no existe: %s", source)
        return 2

    subdir = args.subdir if args.subdir is not None else config.vault_subdir
    tags = args.tag if args.tag else ([config.vault_tag] if config.vault_tag else [])

    logger.info("== Publicar en Obsidian ==")
    logger.info("Origen (.md): %s", source)
    logger.info("Bóveda:       %s", _abs(vault_dir))
    logger.info("Subcarpeta:   %s\n", subdir or "(raíz)")

    summary = vault.publish_folder(
        source_dir=source,
        vault_dir=_abs(vault_dir),
        subdir=subdir,
        extra_tags=tags,
        overwrite=args.overwrite,
        make_index=not args.no_index,
        on_event=lambda status, src, detail: logger.info("  %-5s %s", status.upper(), src),
    )

    logger.info("\nTerminado: %d publicados · %d omitidos · %d con error (de %d).",
                summary["published"], summary["skipped"], summary["failed"], summary["total"])
    if summary["index"]:
        logger.info("Índice: %s", summary["index"])

    print(f"\nBóveda: {summary['dest_dir']}")
    print(f"{summary['published']} publicados · {summary['skipped']} ya existían · "
          f"{summary['failed']} con error.")
    if summary["skipped"] and not args.overwrite:
        print("(Los omitidos ya estaban en la bóveda; usa --overwrite para actualizarlos.)")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
