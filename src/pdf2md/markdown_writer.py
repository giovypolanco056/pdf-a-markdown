"""Serialización del documento a Markdown con YAML Front Matter.

El Front Matter se genera a mano (sin depender de PyYAML) para tener control
total sobre el formato y garantizar acentos correctos (UTF-8).
"""
from __future__ import annotations

from .models import BlockType, DocumentResult


def _yaml_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return '""'
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def render_front_matter(meta: dict) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                lines.extend(f"  - {_yaml_scalar(v)}" for v in value)
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def _render_table(rows: list[list[str]]) -> str:
    def esc(cell) -> str:
        return str(cell).replace("|", "\\|").strip()

    width = max(len(r) for r in rows)
    norm = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(esc(c) for c in norm[0]) + " |",
           "| " + " | ".join(["---"] * width) + " |"]
    for r in norm[1:]:
        out.append("| " + " | ".join(esc(c) for c in r) + " |")
    return "\n".join(out)


def render_document(doc: DocumentResult, include_page_markers: bool = True) -> str:
    parts = [render_front_matter(doc.metadata), ""]
    for page in doc.pages:
        if include_page_markers:
            parts.append(f"<!-- página {page.number} -->")
        for block in page.blocks:
            if block.type == BlockType.HEADING:
                level = min(max(block.level, 1), 6)
                parts.append(f"{'#' * level} {block.text}")
            elif block.type == BlockType.PARAGRAPH:
                parts.append(block.text)
            elif block.type == BlockType.LIST:
                for idx, item in enumerate(block.items, start=1):
                    parts.append(f"{idx}. {item}" if block.ordered else f"- {item}")
            elif block.type == BlockType.TABLE:
                parts.append(_render_table(block.rows))
            parts.append("")   # separación entre bloques

    text = "\n".join(parts)
    while "\n\n\n" in text:    # colapsar líneas en blanco de más
        text = text.replace("\n\n\n", "\n\n")
    return text.strip() + "\n"
