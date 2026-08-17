#!/usr/bin/env python3
"""Detecta y escribe relaciones semánticas entre las notas de la bóveda (Fase 2.6).

Analiza el contenido de cada nota ya publicada y las enlaza cuando tratan del
mismo tema, proyecto, entidad o evento —aunque no usen las mismas palabras—.
El resultado se ve en Obsidian: tags (tema/…, evento/…), keywords, la propiedad
`related`, una sección "🔗 Notas relacionadas" con enlaces y su nivel de
confianza, y mapas por tema (Tema - X). Prioriza la PRECISIÓN: pocas relaciones,
pero buenas.

Ejecutar:  python relacionar.py            (usa vault_dir de config.yaml)
           o:  python relacionar.py -d "C:\\ruta\\a\\tu\\Boveda"
           o doble clic en  relacionar.bat

NO es destructivo: sólo reescribe el front matter y esa sección marcada de cada
nota. Es idempotente y ejecutarlo de nuevo sólo re-analiza lo que cambió.

>>> AJUSTES <<<
    - Umbral y tope de enlaces:  relate_threshold / relate_top_k  en config.yaml.
    - Conocimiento del dominio:  edita  src/pdf2md/semantics/data/conceptos.yaml
      (o apunta relate_lexicon a tu propio archivo).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from pdf2md.config import Config          # noqa: E402
from pdf2md.errors import get_logger      # noqa: E402
from pdf2md.semantics.lexicon import Lexicon        # noqa: E402
from pdf2md.semantics.relate import RelateParams, relacionar_boveda  # noqa: E402


def _abs(p) -> Path:
    p = Path(p)
    return p if p.is_absolute() else (PROJECT_DIR / p)


def main(argv=None) -> int:
    config = Config.load(str(PROJECT_DIR / "config.yaml"))

    ap = argparse.ArgumentParser(
        description="Relaciona las notas de la bóveda por tema, proyecto, entidad y evento.")
    ap.add_argument("-d", "--vault", help="Carpeta raíz de la bóveda de Obsidian")
    ap.add_argument("--subdir", help="Subcarpeta dentro de la bóveda (\"\" para la raíz)")
    ap.add_argument("--threshold", type=float, help="Confianza mínima 0-1 (por defecto 0.22)")
    ap.add_argument("--top-k", type=int, help="Máximo de enlaces por nota")
    ap.add_argument("--lexicon", help="Ruta a un conceptos.yaml propio")
    ap.add_argument("--embeddings", action="store_true",
                    help="Activar embeddings (requiere sentence-transformers)")
    args = ap.parse_args(argv)

    logger = get_logger()

    vault_dir = args.vault or config.vault_dir
    if not vault_dir:
        logger.error('No hay bóveda configurada. Indica  --vault "C:\\ruta"  '
                     "o pon  vault_dir  en config.yaml.")
        return 2
    subdir = args.subdir if args.subdir is not None else config.vault_subdir

    params = RelateParams.from_config(config)
    if args.threshold is not None:
        params.threshold = args.threshold
    if args.top_k is not None:
        params.top_k = args.top_k
    if args.lexicon:
        params.lexicon_path = args.lexicon
    if args.embeddings:
        params.use_embeddings = True

    lex = Lexicon.load(params.lexicon_path)
    if not lex.concepts:
        logger.warning("El léxico de conceptos está vacío (¿falta PyYAML o el archivo?). "
                       "Se relacionará sólo por texto y entidades.")

    logger.info("== Relacionar notas (capa semántica) ==")
    logger.info("Bóveda:     %s", _abs(vault_dir))
    logger.info("Subcarpeta: %s", subdir or "(raíz)")
    logger.info("Umbral:     %d%%  ·  máx. %d enlaces/nota  ·  %d conceptos, %d eventos\n",
                round(params.threshold * 100), params.top_k, len(lex.concepts), len(lex.events))

    summary = relacionar_boveda(_abs(vault_dir), subdir, params=params, lex=lex)

    n_rel = len(summary["relations"])
    logger.info("Terminado: %d notas · %d relaciones · %d mapas de tema.",
                summary["total"], n_rel, summary["temas"])
    if summary.get("reused"):
        logger.info("(%d notas sin cambios se reutilizaron del índice.)", summary["reused"])

    # Muestra las relaciones más fuertes para revisión rápida
    top = sorted(summary["relations"], key=lambda r: -r["confidence"])[:12]
    if top:
        print("\nRelaciones más fuertes:")
        for r in top:
            print(f"  {round(r['confidence'] * 100):3d}%  {r['a']}  ↔  {r['b']}  "
                  f"({', '.join(r['reasons'])})")

    print(f"\nBóveda: {summary['dest']}")
    print(f"{summary['total']} notas · {n_rel} relaciones · {summary['temas']} mapas de tema.")
    print("Abre Obsidian: mira los tags 'tema/…', el 'Mapa de Temas' y el Graph View.")
    print("Detalle por nota en el archivo de auditoría  _relaciones.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
