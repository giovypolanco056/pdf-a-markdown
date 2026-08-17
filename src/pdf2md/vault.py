"""Publicación de los Markdown en una bóveda de Obsidian (Fase 2).

Una bóveda de Obsidian NO es un formato especial ni un servidor: es sólo una
carpeta con archivos ``.md``. "Publicar" consiste en copiar cada ``.md`` a esa
carpeta, dejándolos bien integrados:

  * un nombre de nota seguro para Obsidian (sin caracteres prohibidos),
  * el front matter enriquecido (``aliases`` + ``tags``) para que Obsidian lo
    indexe y lo encuentres por su título,
  * un índice navegable (``Índice.md`` con wikilinks) y un ``_indice.jsonl``
    que servirá de puente hacia el retriever del RAG (Fase 3).

Por defecto NO se sobrescriben notas que ya existan en la bóveda (para no pisar
lo que hayas editado dentro de Obsidian); usa ``overwrite=True`` para forzarlo.
El índice, en cambio, se regenera siempre.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import unicodedata
from pathlib import Path

from .markdown_writer import render_front_matter

try:
    import yaml  # PyYAML: necesario para leer el front matter existente.
except ImportError:  # pragma: no cover
    yaml = None


# Caracteres que Obsidian no admite (o interpreta mal) en el nombre de una nota.
_FORBIDDEN = r'[\\/:*?"<>|#^\[\]]'
_INDEX_NAME = "Índice"        # nombre de la nota-índice dentro de la bóveda
_JSONL_NAME = "_indice.jsonl"  # índice de sistema (puente al RAG)


# --------------------------------------------------------------------------- #
# Nombres y front matter
# --------------------------------------------------------------------------- #
def slugify_filename(name: str, max_len: int = 120) -> str:
    """Convierte un texto en un nombre de archivo seguro y legible para Obsidian.

    Mantiene acentos y mayúsculas (Obsidian los admite y son más legibles para
    ti); sólo elimina los caracteres prohibidos y colapsa los espacios.
    """
    name = re.sub(_FORBIDDEN, " ", name)
    name = re.sub(r"\s+", " ", name).strip(" .")   # sin espacios dobles ni punto final
    if len(name) > max_len:
        name = name[:max_len].rstrip(" .")
    return name or "documento"


def split_front_matter(text: str) -> tuple[dict, str]:
    """Separa el front matter YAML (como dict) del cuerpo del Markdown.

    Si no hay front matter, o no se puede parsear, devuelve ``({}, texto)``.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            block = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1:]).lstrip("\n")
            meta: dict = {}
            if yaml is not None:
                try:
                    loaded = yaml.safe_load(block)
                    if isinstance(loaded, dict):
                        meta = loaded
                except yaml.YAMLError:
                    meta = {}
            return meta, body
    return {}, text


def enrich_front_matter(meta: dict, extra_tags: list[str]) -> dict:
    """Devuelve una copia del front matter lista para Obsidian.

    - ``aliases``: añade el título, para encontrar la nota por su nombre real.
    - ``tags``: añade ``extra_tags`` (p. ej. ``pdf-importado``) sin duplicar.
    No se elimina ni se altera ningún otro campo existente.
    """
    meta = dict(meta)   # no mutar el original

    title = meta.get("title")
    if title:
        aliases = meta.get("aliases") or []
        if not isinstance(aliases, list):
            aliases = [aliases]
        if title not in aliases:
            aliases = [title, *aliases]
        meta["aliases"] = aliases

    tags = meta.get("tags") or []
    if not isinstance(tags, list):
        tags = [tags]
    for tag in extra_tags:
        clean = _clean_tag(tag)
        if clean and clean not in tags:
            tags.append(clean)
    meta["tags"] = tags
    return meta


def _clean_tag(tag: str) -> str:
    """Un tag de Obsidian no admite espacios; se sustituyen por guiones."""
    return re.sub(r"\s+", "-", str(tag).strip().lstrip("#"))


# --------------------------------------------------------------------------- #
# Publicación de un archivo
# --------------------------------------------------------------------------- #
def publish_markdown_file(md_path: Path, dest_dir: Path, extra_tags: list[str],
                          overwrite: bool = False) -> dict:
    """Publica un único ``.md`` en la carpeta destino de la bóveda.

    Devuelve un dict con ``name`` (nombre final de la nota, sin extensión),
    ``title``, ``status`` ("ok"/"skip"), ``source`` (nombre original) y ``meta``.
    """
    text = md_path.read_text(encoding="utf-8")
    meta, body = split_front_matter(text)
    title = str(meta.get("title") or md_path.stem)

    note_name = slugify_filename(md_path.stem)   # el nombre del PDF, ya saneado
    dest = dest_dir / f"{note_name}.md"

    info = {"name": note_name, "title": title, "source": md_path.name, "meta": meta}
    if dest.exists() and not overwrite:
        return {**info, "status": "skip"}

    if meta:
        content = render_front_matter(enrich_front_matter(meta, extra_tags)) + "\n\n" + body
        if not content.endswith("\n"):
            content += "\n"
    else:
        content = text   # sin front matter parseable: se copia tal cual

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return {**info, "status": "ok"}


# --------------------------------------------------------------------------- #
# Índices (navegable + de sistema)
# --------------------------------------------------------------------------- #
def _wikilink(name: str, title: str) -> str:
    """Enlace ``[[archivo|Título]]`` (o ``[[archivo]]`` si coinciden)."""
    alias = re.sub(r"[\[\]|]", " ", title).strip()
    return f"[[{name}|{alias}]]" if alias and alias != name else f"[[{name}]]"


def render_index(entries: list[dict], titulo: str) -> str:
    today = _dt.date.today().isoformat()
    published = sorted((e for e in entries if e["status"] in ("ok", "skip")),
                       key=lambda e: e["title"].lower())

    lines = [
        render_front_matter({"title": f"Índice — {titulo}", "tags": ["índice"]}),
        "",
        f"# Índice — {titulo}",
        "",
        f"> {len(published)} documento(s) · actualizado {today}",
        "",
    ]
    for e in published:
        meta = e.get("meta") or {}
        bits: list[str] = []
        if meta.get("pages"):
            bits.append(f"{meta['pages']} pág.")
        if meta.get("ocr"):
            conf = meta.get("ocr_confidence")
            bits.append(f"OCR {conf}%" if conf else "OCR")
        if meta.get("date_processed"):
            bits.append(f"procesado {meta['date_processed']}")
        suffix = f" — {' · '.join(bits)}" if bits else ""
        lines.append(f"- {_wikilink(e['name'], e['title'])}{suffix}")
    lines.append("")
    return "\n".join(lines)


def write_index_jsonl(entries: list[dict], path: Path) -> None:
    """Vuelca un registro por documento (puente hacia el retriever del RAG)."""
    with path.open("w", encoding="utf-8") as fh:
        for e in entries:
            if e["status"] not in ("ok", "skip"):
                continue
            meta = e.get("meta") or {}
            fh.write(json.dumps({
                "note": e["name"],
                "title": e["title"],
                "source": e.get("source"),
                "pages": meta.get("pages"),
                "ocr": meta.get("ocr"),
                "language": meta.get("language"),
                "date_processed": meta.get("date_processed"),
            }, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# Publicación de una carpeta completa
# --------------------------------------------------------------------------- #
def publish_folder(source_dir, vault_dir, subdir: str = "PDF importados",
                   extra_tags: list[str] | None = None, overwrite: bool = False,
                   make_index: bool = True, on_event=None) -> dict:
    """Publica todos los ``.md`` de ``source_dir`` en la bóveda ``vault_dir``.

    ``subdir`` es la subcarpeta dentro de la bóveda (usa "" para la raíz).
    ``on_event(status, source, detalle)`` notifica cada archivo (status en
    {"ok","skip","error"}). Devuelve un resumen con contadores y rutas.
    """
    source_dir = Path(source_dir)
    dest_dir = Path(vault_dir) / subdir if subdir else Path(vault_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    tags = extra_tags if extra_tags is not None else ["pdf-importado"]

    mds = sorted(p for p in source_dir.glob("*.md")
                 if not p.name.startswith("_") and p.stem != _INDEX_NAME)

    entries: list[dict] = []
    ok = skipped = failed = 0
    for md in mds:
        try:
            info = publish_markdown_file(md, dest_dir, tags, overwrite)
        except Exception as exc:   # un archivo roto no debe frenar el lote
            info = {"name": md.stem, "title": md.stem, "source": md.name,
                    "meta": {}, "status": "error", "error": f"{exc.__class__.__name__}: {exc}"}
        entries.append(info)
        ok += info["status"] == "ok"
        skipped += info["status"] == "skip"
        failed += info["status"] == "error"
        if on_event:
            on_event(info["status"], info["source"], info.get("error") or info["name"])

    index_path = None
    if make_index and entries:
        index_path = dest_dir / f"{_INDEX_NAME}.md"
        index_path.write_text(render_index(entries, subdir or Path(vault_dir).name),
                              encoding="utf-8")
        write_index_jsonl(entries, dest_dir / _JSONL_NAME)

    return {"published": ok, "skipped": skipped, "failed": failed,
            "total": len(entries), "dest_dir": str(dest_dir),
            "index": str(index_path) if index_path else None, "entries": entries}


# --------------------------------------------------------------------------- #
# Organización por temas (mapas MOC para conectar el grafo de Obsidian)
# --------------------------------------------------------------------------- #
_MOC_PREFIX = "Mapa - "

# Cada nota se agrupa por el formato del que vino. El conversor guarda ese dato en
# el campo `file_type` del front matter (pdf / docx / xlsx); aquí se traduce a un
# nombre legible para el apartado y el tag.
_FORMATO_NOMBRE: dict[str, str] = {"pdf": "PDF", "docx": "Word", "xlsx": "Excel"}


def _slug_tag(s: str) -> str:
    """Normaliza un tema a un tag válido de Obsidian: sin acentos ni espacios."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "general"


def clasificar_origen(meta: dict) -> str:
    """Grupo de la nota según su formato de origen (PDF / Word / Excel / Otros)."""
    ft = str(meta.get("file_type", "")).lower()
    if ft in _FORMATO_NOMBRE:
        return _FORMATO_NOMBRE[ft]
    src = str(meta.get("source", "")).lower()   # respaldo: por la extensión del original
    for ext, nombre in ((".pdf", "PDF"), (".docx", "Word"), (".xlsx", "Excel")):
        if src.endswith(ext):
            return nombre
    return "Otros"


def _add_tags(meta: dict, nuevos: list[str]) -> dict:
    meta = dict(meta)
    tags = meta.get("tags") or []
    if not isinstance(tags, list):
        tags = [tags]
    for tg in nuevos:
        if tg and tg not in tags:
            tags.append(tg)
    meta["tags"] = tags
    return meta


def organizar_boveda(vault_dir, subdir: str = "PDF importados", on_event=None) -> dict:
    """Agrupa las notas por su formato de origen y teje el grafo de Obsidian.

    Cada nota se clasifica por el formato del que vino (PDF, Word o Excel, según
    el campo ``file_type``). Por cada nota: añade el tag ``origen/<slug>`` (sin
    borrar otros tags). Por cada grupo: crea un mapa ``Mapa - <grupo>.md`` que
    enlaza sus documentos. Regenera el ``Índice.md`` enlazando los mapas. El
    grafo pasa de nodos sueltos a un racimo por formato colgando del índice.
    """
    dest = Path(vault_dir) / subdir if subdir else Path(vault_dir)

    # Se excluyen los índices y TODOS los mapas: los de formato (Mapa - …) y los
    # de la capa semántica (Tema - …, Mapa de Temas), que gobierna relacionar.py.
    notas = [m for m in sorted(dest.glob("*.md"))
             if m.stem != _INDEX_NAME and not m.stem.startswith(_MOC_PREFIX)
             and not m.stem.startswith("Tema - ") and m.stem != "Mapa de Temas"
             and not m.name.startswith("_")]

    for viejo in dest.glob(f"{_MOC_PREFIX}*.md"):   # borra mapas de ejecuciones previas
        viejo.unlink()

    grupos: dict[str, list[tuple[str, str]]] = {}
    for md in notas:
        text = md.read_text(encoding="utf-8")
        meta, body = split_front_matter(text)
        title = str(meta.get("title") or md.stem)
        grupo = clasificar_origen(meta)
        if meta:   # re-sellar SÓLO el tag de origen (namespace propio)
            # No se tocan los tags de la capa semántica (tema/ evento/ entidad/):
            # cada capa gobierna su propio namespace y así conviven sin pisarse.
            prev = [t for t in (meta.get("tags") or [])
                    if not str(t).startswith("origen/")]
            meta = {**meta, "tags": prev}
            nueva = _add_tags(meta, ["origen/" + _slug_tag(grupo)])
            content = render_front_matter(nueva) + "\n\n" + body.lstrip("\n")
            md.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
        grupos.setdefault(grupo, []).append((md.stem, title))
        if on_event:
            on_event(grupo, md.name)

    # Un mapa (MOC) por tema
    mocs: list[tuple[str, str, int]] = []
    for grupo in sorted(grupos):
        items = sorted(grupos[grupo], key=lambda x: x[1].lower())
        moc_name = f"{_MOC_PREFIX}{grupo}"
        lines = [render_front_matter({"title": f"Mapa — {grupo}",
                                      "tags": ["moc", "origen/" + _slug_tag(grupo)]}),
                 "", f"# {grupo}", "", f"> {len(items)} documento(s)", ""]
        lines += [f"- {_wikilink(stem, title)}" for stem, title in items]
        lines.append("")
        (dest / f"{moc_name}.md").write_text("\n".join(lines), encoding="utf-8")
        mocs.append((moc_name, grupo, len(items)))

    # Índice maestro que enlaza los mapas
    total = sum(len(v) for v in grupos.values())
    nombre = subdir or Path(vault_dir).name
    lines = [render_front_matter({"title": f"Índice — {nombre}", "tags": ["moc", "índice"]}),
             "", f"# Índice — {nombre}", "",
             f"> {total} documento(s) en {len(mocs)} apartados · actualizado {_dt.date.today().isoformat()}",
             ""]
    for moc_name, grupo, n in sorted(mocs, key=lambda x: (-x[2], x[1].lower())):
        lines.append(f"- [[{moc_name}|{grupo}]] ({n})")
    lines.append("")
    (dest / f"{_INDEX_NAME}.md").write_text("\n".join(lines), encoding="utf-8")

    return {"total": total, "grupos": {g: len(v) for g, v in grupos.items()},
            "mocs": len(mocs), "dest": str(dest)}
