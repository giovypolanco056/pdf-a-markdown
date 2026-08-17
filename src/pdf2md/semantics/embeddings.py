"""Backend OPCIONAL de embeddings (similitud semántica con un modelo de lenguaje).

El motor de relaciones funciona perfectamente sin esto (TF-IDF + léxico). Este
módulo es la vía de crecimiento: si algún día instalas `sentence-transformers`
(requiere un Python con wheels de PyTorch — hoy tu entorno es 3.14 y aún no las
hay), el motor puede añadir una señal de similitud semántica "de verdad" por
encima de las demás, reutilizando el contrato `BaseEmbedder` que ya estaba
esbozado para el RAG (Fase 3).

Se importa de forma perezosa y tolerante: si la librería no está, `get_embedder`
devuelve None y el motor sigue con las señales sin-dependencias.
"""
from __future__ import annotations

from ..rag.interfaces import BaseEmbedder


class SentenceTransformerEmbedder(BaseEmbedder):
    """Implementación de `BaseEmbedder` sobre sentence-transformers (multilingüe)."""

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        from sentence_transformers import SentenceTransformer  # import perezoso
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, v)) for v in vecs]


def get_embedder(model_name: str | None = None):
    """Devuelve un embedder listo, o None si la librería/modelo no está disponible."""
    try:
        return SentenceTransformerEmbedder(model_name) if model_name else SentenceTransformerEmbedder()
    except Exception:   # ImportError, modelo no descargable, incompatibilidad de versión…
        return None
