"""Capa semántica: detecta relaciones entre notas Markdown (Fase 2.6).

Esta capa se ejecuta DESPUÉS de publicar y organizar la bóveda. Lee los `.md`
ya publicados, analiza su contenido y **teje relaciones** entre documentos que
tratan del mismo tema, proyecto, entidad o evento —aunque no usen exactamente
las mismas palabras— y las materializa en Obsidian (tags, wikilinks, MOCs).

Principios de diseño:
  * **No destructiva:** sólo reescribe el front matter y una sección marcada
    del cuerpo; nunca borra el contenido convertido.
  * **Sin dependencias pesadas:** funciona con la librería estándar + PyYAML.
    Los embeddings son un extra opcional (ver `embeddings.py`).
  * **Precisión > cantidad:** cada relación lleva un nivel de confianza y sólo
    las que superan un umbral se convierten en enlaces.
  * **Escalable:** el conocimiento del dominio vive en `data/conceptos.yaml`
    (datos, no código); crece editando ese archivo.

Punto de entrada principal: `relate.relacionar_boveda(...)`.
"""
from __future__ import annotations

__all__ = ["relate", "lexicon", "entities", "normalize", "profile"]
