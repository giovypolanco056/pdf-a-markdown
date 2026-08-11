"""Carga de configuración (config.yaml + valores por defecto)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import yaml  # PyYAML es opcional: si falta, se usan los valores por defecto.
except ImportError:  # pragma: no cover
    yaml = None


@dataclass
class Config:
    # Carpetas
    input_dir: str = "documentos/originales"
    output_dir: str = "documentos/markdown"
    errors_dir: str = "documentos/errores"

    # Idioma
    language: str = "es"       # etiqueta para los metadatos del Markdown
    ocr_lang: str = "spa"      # código de idioma de Tesseract (spa = español)

    # Detección digital vs. escaneado
    min_chars_text: int = 100  # caracteres alfanuméricos mínimos por página "digital"

    # OCR
    ocr_dpi: int = 300
    tesseract_cmd: str | None = None   # ruta al ejecutable (None = automático/PATH)
    tessdata_dir: str | None = None    # carpeta con los .traineddata (None = la de Tesseract)
    min_ocr_conf: float = 60.0         # umbral para marcar palabras dudosas

    # Estructura / Markdown
    detect_tables: bool = True
    remove_headers_footers: bool = True
    include_page_markers: bool = True  # comentarios <!-- página N --> (útil para RAG)

    # Procesamiento por lotes
    recursive: bool = False
    overwrite: bool = False

    # Modo automático (vigilancia de carpeta)
    watch_dir: str = "documentos/entrada"        # se dejan aquí los PDF nuevos
    processed_dir: str = "documentos/procesados"  # los PDF ya convertidos se mueven aquí

    @classmethod
    def load(cls, path: str | Path | None = "config.yaml") -> "Config":
        cfg = cls()
        if path is None or yaml is None:
            return cfg
        p = Path(path)
        if not p.exists():
            return cfg
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for key, value in data.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        return cfg

    def as_dict(self) -> dict:
        return asdict(self)
