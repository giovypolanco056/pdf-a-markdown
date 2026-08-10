"""Interfaces preparadas para la Fase 3/4 (RAG).

Este módulo demuestra que el Markdown generado en la Fase 1 YA está listo para
RAG, sin implementar todavía embeddings ni bases de datos vectoriales:

  * `Chunk`          -> la unidad que se indexará (texto + procedencia).
  * `HeadingChunker` -> divide el .md por secciones de título (implementado,
                        sin dependencias externas).
  * `BaseEmbedder` / `BaseVectorStore` -> contratos vacíos (Fase 3), a rellenar
                        más adelante con, p. ej., sentence-transformers + FAISS
                        o Chroma.

Cuando se construya el RAG, el flujo será:
    Markdown -> HeadingChunker -> Embedder -> VectorStore -> Retriever -> LLM
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_PAGE_RE = re.compile(r"<!--\s*página\s+(\d+)\s*-->")
_FRONT_MATTER_RE = re.compile(r"^---\n.*?\n---\n", re.S)


@dataclass
class Chunk:
    """Fragmento indexable. `heading_path` y `page` permiten citar la fuente."""
    text: str
    source: str
    heading_path: list[str] = field(default_factory=list)
    page: int | None = None
    metadata: dict = field(default_factory=dict)


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, markdown: str, source: str) -> list[Chunk]:
        ...


class HeadingChunker(BaseChunker):
    """Divide el Markdown en fragmentos: uno por sección de título.

    Conserva la ruta de títulos (heading_path) y el número de página de origen,
    que serán la base de las citas del futuro sistema RAG.
    """

    def __init__(self, max_chars: int = 1500):
        self.max_chars = max_chars

    def chunk(self, markdown: str, source: str) -> list[Chunk]:
        body = _FRONT_MATTER_RE.sub("", markdown, count=1)
        chunks: list[Chunk] = []
        stack: list[tuple[int, str]] = []
        buf: list[str] = []
        page: int | None = None

        def flush() -> None:
            text = "\n".join(buf).strip()
            if text:
                for piece in self._split_long(text):
                    chunks.append(Chunk(text=piece, source=source,
                                        heading_path=[h for _, h in stack], page=page))
            buf.clear()

        for line in body.splitlines():
            pm = _PAGE_RE.search(line)
            if pm:
                page = int(pm.group(1))
                continue
            hm = _HEADING_RE.match(line)
            if hm:
                flush()
                level = len(hm.group(1))
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, hm.group(2).strip()))
            else:
                buf.append(line)
        flush()
        return chunks

    def _split_long(self, text: str) -> list[str]:
        if len(text) <= self.max_chars:
            return [text]
        parts, current = [], ""
        for para in text.split("\n\n"):
            if current and len(current) + len(para) > self.max_chars:
                parts.append(current.strip())
                current = ""
            current += para + "\n\n"
        if current.strip():
            parts.append(current.strip())
        return parts


class BaseEmbedder(ABC):
    """Fase 3: convertir texto en vectores. NO implementado en la Fase 1."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class BaseVectorStore(ABC):
    """Fase 3/4: almacenar y buscar vectores. NO implementado en la Fase 1."""

    @abstractmethod
    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, query_vector: list[float], k: int = 5) -> list[Chunk]:
        raise NotImplementedError
