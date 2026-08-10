"""OCR de páginas escaneadas con Tesseract (vía pytesseract).

Estrategia:
  * Se renderiza la página a imagen (DPI configurable) con PyMuPDF.
  * `image_to_data` devuelve cada palabra con su bloque/párrafo/línea, su
    posición, su altura y su nivel de confianza.
  * Se reconstruyen párrafos, listas y (heurísticamente) títulos a partir de
    esa información de posición y tamaño.
  * Las palabras con confianza baja NO se corrigen "inventando": se registran
    como avisos para que el usuario pueda revisarlas.
"""
from __future__ import annotations

import io
import os
import shutil
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from . import textutils as tu
from .errors import OCRUnavailableError
from .models import Block, BlockType

try:
    import pytesseract
    from pytesseract import Output
except ImportError:  # pragma: no cover
    pytesseract = None
    Output = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def ensure_tesseract(tesseract_cmd: str | None = None,
                     tessdata_dir: str | None = None,
                     lang: str | None = None) -> None:
    """Verifica que el OCR se pueda usar; si no, lanza OCRUnavailableError."""
    if pytesseract is None:
        raise OCRUnavailableError("pytesseract no está instalado. Ejecuta: pip install pytesseract")
    if Image is None:
        raise OCRUnavailableError("Pillow no está instalado. Ejecuta: pip install Pillow")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    exe = pytesseract.pytesseract.tesseract_cmd
    if shutil.which(exe) is None and shutil.which("tesseract") is None:
        raise OCRUnavailableError(
            "No se encontró el ejecutable de Tesseract. Instálalo y/o define "
            "'tesseract_cmd' en config.yaml. En Windows suele estar en "
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
    if tessdata_dir:
        td = Path(tessdata_dir)
        if not td.exists():
            raise OCRUnavailableError(f"La carpeta 'tessdata_dir' no existe: {td.resolve()}")
        if lang:
            missing = [l for l in lang.split("+") if not (td / f"{l}.traineddata").exists()]
            if missing:
                raise OCRUnavailableError(
                    f"Faltan idiomas en {td.resolve()}: {', '.join(missing)}. "
                    "Descárgalos de https://github.com/tesseract-ocr/tessdata"
                )


def _render(page, dpi: int):
    pix = page.get_pixmap(dpi=dpi)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def ocr_page(page, lang: str = "spa", dpi: int = 300, min_conf: float = 60.0,
             tessdata_dir: str | None = None):
    """Aplica OCR a una página. Devuelve ``(blocks, confianza_media, avisos)``."""
    # Se usa TESSDATA_PREFIX (variable de entorno) en vez de la opción
    # --tessdata-dir porque pytesseract parte el string de config por espacios
    # y rompería una ruta con espacios (p. ej. "PDF a MD").
    if tessdata_dir:
        os.environ["TESSDATA_PREFIX"] = str(Path(tessdata_dir).resolve())
    data = pytesseract.image_to_data(_render(page, dpi), lang=lang,
                                     output_type=Output.DICT)
    n = len(data["text"])

    # Agrupar palabras por (bloque, párrafo) -> línea -> [palabras]
    paras: dict = defaultdict(lambda: defaultdict(list))
    para_heights: dict = defaultdict(list)
    confs: list[float] = []
    low_conf: list[str] = []
    for i in range(n):
        word = data["text"][i].strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if not word or conf < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i])
        paras[key][data["line_num"][i]].append(word)
        para_heights[key].append(data["height"][i])
        confs.append(conf)
        if conf < min_conf:
            low_conf.append(word)

    # Altura del cuerpo = la altura de texto MÁS FRECUENTE (la del texto normal),
    # más robusta que la mediana cuando hay títulos grandes de por medio.
    all_heights = [round(h) for hs in para_heights.values() for h in hs]
    body_h = Counter(all_heights).most_common(1)[0][0] if all_heights else 0

    blocks: list[Block] = []
    for key in sorted(paras):
        lines_map = paras[key]
        lines = [" ".join(lines_map[ln]) for ln in sorted(lines_map)]
        text = tu.join_lines(lines)
        if not text.strip():
            continue

        # Título ANTES que lista (un título numerado no es una lista de un elemento)
        # Las alturas de caja de Tesseract están "comprimidas" respecto al tamaño
        # de fuente, por eso los umbrales son moderados (1.25 / 1.6).
        ph = statistics.median(para_heights[key]) if para_heights[key] else 0
        is_heading = (len(lines) == 1 and body_h and ph > body_h * 1.25
                      and len(text) <= 80 and not text.endswith((".", ",")))
        if is_heading:
            blocks.append(Block(type=BlockType.HEADING, text=text,
                                level=1 if ph > body_h * 1.6 else 2))
            continue

        if all(tu.is_list_line(l) for l in lines):
            blocks.append(Block(type=BlockType.LIST,
                                items=[tu.strip_list_marker(l) for l in lines],
                                ordered=tu.is_ordered(lines[0])))
            continue

        blocks.append(Block(type=BlockType.PARAGRAPH, text=text))

    confidence = round(statistics.mean(confs), 1) if confs else 0.0
    warnings: list[str] = []
    if low_conf:
        warnings.append(
            f"{len(low_conf)} palabra(s) con baja confianza OCR (<{min_conf:.0f}%). "
            f"Ejemplos: {', '.join(low_conf[:15])}"
        )
    return blocks, confidence, warnings
