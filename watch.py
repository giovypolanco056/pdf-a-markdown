#!/usr/bin/env python3
"""Modo automático: vigila una carpeta y convierte a Markdown los PDF nuevos.

Cuando un PDF llega a la carpeta de ENTRADA:
  * se convierte y el .md se guarda en la carpeta de SALIDA,
  * el PDF original se mueve a PROCESADOS,
  * si algo falla, el PDF se mueve a ERRORES junto con su registro.

Ejecutar:  python watch.py          (Ctrl+C para detener)
           o doble clic en  vigilar.bat

Detecta cuándo un archivo terminó de copiarse comprobando que su tamaño se
mantiene estable entre dos revisiones (evita convertir PDFs a medio copiar).
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from pdf2md.config import Config                       # noqa: E402
from pdf2md.errors import get_logger, record_failure   # noqa: E402
from pdf2md.markdown_writer import render_document      # noqa: E402
from pdf2md.pipeline import convert_pdf, _write_warnings  # noqa: E402


def _abs(p) -> Path:
    p = Path(p)
    return p if p.is_absolute() else (PROJECT_DIR / p)


def _unique(path: Path) -> Path:
    """Devuelve una ruta que no exista, añadiendo _1, _2… si hace falta."""
    if not path.exists():
        return path
    i = 1
    while True:
        cand = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not cand.exists():
            return cand
        i += 1


def process_pdf(pdf: Path, config: Config, output_dir: Path, processed_dir: Path,
                errors_dir: Path, logger, overwrite: bool) -> tuple[str, str]:
    """Convierte un PDF y lo archiva. Devuelve ("ok", nombre_md) o ("error", detalle)."""
    logger.info("Nuevo PDF: %s", pdf.name)
    out = output_dir / f"{pdf.stem}.md"
    if out.exists() and not overwrite:
        out = _unique(out)
    try:
        result = convert_pdf(pdf, config)
        out.write_text(render_document(result, config.include_page_markers), encoding="utf-8")
        if result.warnings or any(p.warnings for p in result.pages):
            _write_warnings(errors_dir, pdf, result)
        shutil.move(str(pdf), str(_unique(processed_dir / pdf.name)))
        logger.info("  OK    %s   (original -> %s/)", out.name, processed_dir.name)
        return "ok", out.name
    except Exception as exc:
        record_failure(errors_dir, pdf, exc)
        try:
            shutil.move(str(pdf), str(_unique(errors_dir / pdf.name)))
        except OSError:
            pass
        logger.error("  FALLO %s  (%s: %s)  (movido a %s/)",
                     pdf.name, exc.__class__.__name__, exc, errors_dir.name)
        return "error", f"{exc.__class__.__name__}: {exc}"


def _responsive_sleep(interval: float, stop_event) -> None:
    """Duerme `interval` segundos pero atendiendo la señal de parada cada 0.2s."""
    end = time.monotonic() + interval
    while time.monotonic() < end:
        if stop_event is not None and stop_event.is_set():
            return
        time.sleep(min(0.2, max(0.0, end - time.monotonic())))


def watch(config: Config, watch_dir: Path, output_dir: Path, processed_dir: Path,
          errors_dir: Path, interval: float, logger, overwrite: bool,
          stop_event=None, on_event=None) -> None:
    """Bucle de vigilancia.

    ``stop_event`` (threading.Event) permite detenerlo desde otro hilo (la GUI).
    ``on_event(kind, a, b)`` notifica actividad: kinds "started"/"ok"/"error"/"stopped".
    """
    for d in (watch_dir, output_dir, processed_dir, errors_dir):
        d.mkdir(parents=True, exist_ok=True)

    logger.info("== Modo vigilancia ==")
    logger.info("Entrada:    %s", watch_dir)
    logger.info("Salida:     %s", output_dir)
    logger.info("Procesados: %s", processed_dir)
    logger.info("Revisando cada %ss. Pulsa Ctrl+C para detener.\n", interval)
    if on_event:
        on_event("started", str(watch_dir), str(output_dir))

    sizes: dict[Path, int] = {}
    stable: dict[Path, int] = {}
    while not (stop_event is not None and stop_event.is_set()):
        try:
            pdfs = sorted(watch_dir.glob("*.pdf"))
        except OSError:
            pdfs = []
        for pdf in pdfs:
            if stop_event is not None and stop_event.is_set():
                break
            try:
                size = pdf.stat().st_size
            except OSError:
                continue
            # ¿tamaño estable respecto a la revisión anterior?
            if size > 0 and sizes.get(pdf) == size:
                stable[pdf] = stable.get(pdf, 0) + 1
            else:
                stable[pdf] = 0
            sizes[pdf] = size

            if stable.get(pdf, 0) >= 1:   # mismo tamaño en 2 lecturas seguidas
                status, info = process_pdf(pdf, config, output_dir, processed_dir,
                                           errors_dir, logger, overwrite)
                sizes.pop(pdf, None)
                stable.pop(pdf, None)
                if on_event:
                    on_event(status, pdf.name, info)
        _responsive_sleep(interval, stop_event)

    if on_event:
        on_event("stopped", "", "")


def main(argv=None) -> int:
    config = Config.load(str(PROJECT_DIR / "config.yaml"))

    ap = argparse.ArgumentParser(
        description="Vigila una carpeta y convierte PDF→Markdown automáticamente.")
    ap.add_argument("-w", "--watch", help="Carpeta a vigilar (entrada)")
    ap.add_argument("-o", "--output", help="Carpeta de salida .md")
    ap.add_argument("-p", "--processed", help="Carpeta para los PDF ya procesados")
    ap.add_argument("--interval", type=float, default=3.0, help="Segundos entre revisiones")
    ap.add_argument("--overwrite", action="store_true", help="Sobrescribir .md con el mismo nombre")
    ap.add_argument("--tesseract", help="Ruta al ejecutable de Tesseract")
    args = ap.parse_args(argv)

    if args.tesseract:
        config.tesseract_cmd = args.tesseract
    if config.tessdata_dir:                    # rutas absolutas: funciona desde cualquier CWD
        config.tessdata_dir = str(_abs(config.tessdata_dir))
    config.errors_dir = str(_abs(config.errors_dir))

    logger = get_logger()
    try:
        watch(config,
              _abs(args.watch or config.watch_dir),
              _abs(args.output or config.output_dir),
              _abs(args.processed or config.processed_dir),
              _abs(config.errors_dir),
              args.interval, logger, args.overwrite)
    except KeyboardInterrupt:
        logger.info("\nDetenido por el usuario. ¡Hasta luego!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
