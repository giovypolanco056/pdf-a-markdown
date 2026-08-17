#!/usr/bin/env python3
"""Organiza la bóveda de Obsidian por formato de origen (Fase 2).

Agrupa cada nota según de dónde vino (PDF, Word o Excel), le pone un tag
``origen/<algo>``, crea un mapa (MOC) por formato que enlaza sus documentos y
regenera el índice enlazando los mapas. Resultado: en el grafo de Obsidian las
notas dejan de estar sueltas y se agrupan en un racimo por formato.

Ejecutar:  python organizar.py          (usa vault_dir de config.yaml)
           o:  python organizar.py -d "C:\\ruta\\a\\tu\\Boveda"

El formato se lee del campo file_type del front matter (lo escribe el conversor).
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

    ap = argparse.ArgumentParser(description="Organiza la bóveda de Obsidian por temas.")
    ap.add_argument("-d", "--vault", help="Carpeta raíz de la bóveda de Obsidian")
    ap.add_argument("--subdir", help="Subcarpeta dentro de la bóveda (\"\" para la raíz)")
    args = ap.parse_args(argv)

    logger = get_logger()

    vault_dir = args.vault or config.vault_dir
    if not vault_dir:
        logger.error('No hay bóveda configurada. Indica  --vault "C:\\ruta"  '
                     "o pon  vault_dir  en config.yaml.")
        return 2
    subdir = args.subdir if args.subdir is not None else config.vault_subdir

    logger.info("== Organizar bóveda por formato de origen ==")
    logger.info("Bóveda: %s", _abs(vault_dir))
    logger.info("Subcarpeta: %s\n", subdir or "(raíz)")

    summary = vault.organizar_boveda(
        _abs(vault_dir), subdir,
        on_event=lambda tema, nombre: logger.info("  %-22s <- %s", tema, nombre))

    logger.info("\nTerminado: %d documento(s) en %d apartados.", summary["total"], summary["mocs"])
    for grupo, n in sorted(summary["grupos"].items(), key=lambda x: -x[1]):
        logger.info("   %-22s %d", grupo, n)

    print(f"\nBóveda: {summary['dest']}")
    print(f"{summary['total']} documentos organizados en {summary['mocs']} apartados (PDF / Word / Excel).")
    print("Abre 'Índice.md' en Obsidian y mira el grafo: ahora hay un racimo por formato.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
