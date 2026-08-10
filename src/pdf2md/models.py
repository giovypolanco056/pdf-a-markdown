"""Estructuras de datos internas del conversor.

Son deliberadamente simples (dataclasses) para que más adelante sean fáciles
de serializar durante el chunking del sistema RAG (Fase 3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BlockType(str, Enum):
    """Tipos de bloque estructural reconocidos."""
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"


@dataclass
class Block:
    """Un bloque estructural: título, párrafo, lista o tabla."""
    type: BlockType
    text: str = ""                                        # títulos y párrafos
    level: int = 0                                        # nivel de título (1-6)
    ordered: bool = False                                 # lista numerada vs. viñetas
    items: list[str] = field(default_factory=list)        # elementos de una lista
    rows: list[list[str]] = field(default_factory=list)   # filas de una tabla


@dataclass
class Page:
    """Una página ya procesada."""
    number: int
    source: str = "text"                    # "text" (digital) u "ocr" (escaneado)
    blocks: list[Block] = field(default_factory=list)
    ocr_confidence: float | None = None     # 0-100; sólo en páginas OCR
    warnings: list[str] = field(default_factory=list)


@dataclass
class DocumentResult:
    """Resultado completo de convertir un PDF."""
    source_path: str
    pages: list[Page] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def used_ocr(self) -> bool:
        return any(p.source == "ocr" for p in self.pages)
