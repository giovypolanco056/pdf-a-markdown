"""Motor de relaciones: puntúa la afinidad entre notas y la materializa en Obsidian.

Flujo:
    1. Perfila cada nota (reutiliza perfiles sin cambios vía `_semantica.json`).
    2. Construye el corpus (IDF) y vectoriza: TF-IDF, conceptos (con padres) y
       entidades (ponderadas por rareza).
    3. Puntúa cada par de notas con un **nivel de confianza** combinado.
    4. Se queda sólo con las relaciones fuertes (umbral + top-K + corroboración).
    5. Escribe, sin destruir nada, los tags, keywords, `related` y una sección
       `## 🔗 Notas relacionadas` en cada nota; crea los MOCs `Tema - X`.

Diseñado para **precisión > cantidad**: pocas relaciones, pero buenas.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ..markdown_writer import render_front_matter
from ..vault import _wikilink, slugify_filename, split_front_matter
from . import normalize
from .lexicon import Lexicon
from .profile import (DocProfile, build_profile, content_hash, load_index,
                      save_index)

# Marcadores que delimitan NUESTRA sección en el cuerpo (para poder regenerarla
# sin tocar el resto de la nota). Todo lo que haya entre ellos es reemplazable.
_REL_START = "<!-- relaciones:inicio -->"
_REL_END = "<!-- relaciones:fin -->"
_REL_BLOCK_RE = re.compile(re.escape(_REL_START) + r".*?" + re.escape(_REL_END),
                           re.DOTALL)

_MOC_TEMA_PREFIX = "Tema - "
_MAPA_TEMAS = "Mapa de Temas"
_INDEX_NAMES = {"Índice", "Indice", _MAPA_TEMAS}


# --------------------------------------------------------------------------- #
# Parámetros (con valores por defecto calibrados; se pueden ajustar por config)
# --------------------------------------------------------------------------- #
@dataclass
class RelateParams:
    threshold: float = 0.22       # confianza mínima para crear un enlace (0-1)
    top_k: int = 6                # máx. relaciones por nota (evita saturar el grafo)
    keywords_k: int = 8          # nº de keywords por nota
    alpha_parent: float = 0.5    # cuánto irradia un concepto hacia su padre
    tfidf_floor: float = 0.08    # TF-IDF mínimo para contar como señal por sí sola
    concept_tag_min: float = 2.0  # peso mínimo para etiquetar un concepto (una frase o
                                  # una palabra repetida; evita tags por hallazgos sueltos)
    temporal_window: int = 21    # días para considerar dos docs "próximos en tiempo"
    min_entity_df: int = 2       # una entidad conecta si la comparten ≥2 notas
    max_entity_df_frac: float = 0.5   # …y aparece en ≤50% del corpus (si no, es genérica)
    # Pesos de la combinación (suman 1). "evento" y "fecha" son de apoyo: por sí
    # solos NUNCA crean un enlace (regla de corroboración).
    w_tfidf: float = 0.38
    w_concept: float = 0.34
    w_entity: float = 0.18
    w_event: float = 0.05
    w_time: float = 0.05
    # Embeddings opcionales
    use_embeddings: bool = False
    embed_model: str | None = None
    embed_weight: float = 0.40
    lexicon_path: str | None = None

    @classmethod
    def from_config(cls, config) -> "RelateParams":
        p = cls()
        g = lambda k, d: getattr(config, k, d)  # noqa: E731
        p.threshold = float(g("relate_threshold", p.threshold))
        p.top_k = int(g("relate_top_k", p.top_k))
        p.keywords_k = int(g("relate_keywords", p.keywords_k))
        p.use_embeddings = bool(g("relate_use_embeddings", p.use_embeddings))
        p.embed_model = g("relate_embed_model", p.embed_model)
        p.embed_weight = float(g("relate_embed_weight", p.embed_weight))
        p.lexicon_path = g("relate_lexicon", p.lexicon_path)
        return p


# --------------------------------------------------------------------------- #
# Álgebra dispersa (vectores como dict; sólo stdlib)
# --------------------------------------------------------------------------- #
def _l2_normalize(vec: dict) -> dict:
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: v / norm for k, v in vec.items()}


def _cosine(a: dict, b: dict) -> float:
    """Producto punto de dos vectores YA normalizados = coseno en [0,1]."""
    if len(a) > len(b):
        a, b = b, a
    return sum(w * b.get(k, 0.0) for k, w in a.items())


# --------------------------------------------------------------------------- #
# Perfil "vivo": el DocProfile + sus vectores normalizados para comparar
# --------------------------------------------------------------------------- #
@dataclass
class _Live:
    prof: DocProfile
    ntfidf: dict = field(default_factory=dict)
    nconcept: dict = field(default_factory=dict)
    nentity: dict = field(default_factory=dict)
    embed: list | None = None


def _build_corpus(profiles: dict[str, DocProfile], params: RelateParams):
    """Calcula IDF (términos y entidades), TF-IDF, keywords y vectores normalizados."""
    n = len(profiles)
    # IDF de términos
    df: Counter = Counter()
    for p in profiles.values():
        df.update(p.tf.keys())
    idf = {t: math.log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}

    # IDF de entidades
    edf: Counter = Counter()
    for p in profiles.values():
        edf.update(p.entities.keys())
    eidf = {e: math.log((1 + n) / (1 + d)) + 1.0 for e, d in edf.items()}

    live: dict[str, _Live] = {}
    for name, p in profiles.items():
        # TF-IDF (tf sublineal) + keywords (mostrados con su forma legible)
        tfidf = {t: (1 + math.log(c)) * idf.get(t, 1.0) for t, c in p.tf.items()}
        p.tfidf = tfidf
        top = sorted(tfidf.items(), key=lambda x: -x[1])[:params.keywords_k]
        seen: set[str] = set()
        p.keywords = []
        for t, _ in top:
            kw = p.surface.get(t, t)
            if kw not in seen:
                seen.add(kw)
                p.keywords.append(kw)
        # entidades ponderadas por rareza
        evec = {e: eidf.get(e, 1.0) for e in p.entities}
        live[name] = _Live(prof=p, ntfidf=_l2_normalize(tfidf),
                           nconcept=_l2_normalize(p.concept_vec),
                           nentity=_l2_normalize(evec))
    return live, edf, eidf


def _temporal(pa: DocProfile, pb: DocProfile, window: int) -> float:
    if not pa.doc_date or not pb.doc_date:
        return 0.0
    try:
        da = date.fromisoformat(pa.doc_date)
        db = date.fromisoformat(pb.doc_date)
    except ValueError:
        return 0.0
    days = abs((da - db).days)
    return max(0.0, 1.0 - days / window) if days <= window else 0.0


def _confidence(a: _Live, b: _Live, params: RelateParams) -> tuple[float, list[str]]:
    """Confianza (0-1) de que dos notas están relacionadas + señales que la sostienen."""
    s_tfidf = _cosine(a.ntfidf, b.ntfidf)
    s_concept = _cosine(a.nconcept, b.nconcept)
    s_entity = _cosine(a.nentity, b.nentity)
    same_event = 1.0 if (a.prof.event and a.prof.event == b.prof.event) else 0.0
    s_time = _temporal(a.prof, b.prof, params.temporal_window)
    s_embed = _cosine_list(a.embed, b.embed) if (a.embed and b.embed) else 0.0

    # Regla de corroboración: sin al menos una señal FUERTE (tema, entidad o
    # solapamiento léxico real), no hay enlace. "evento"/"fecha" no bastan solos.
    strong = (s_concept > 0.0) or (s_entity > 0.0) or (s_tfidf >= params.tfidf_floor) \
        or (s_embed >= 0.35)
    if not strong:
        return 0.0, []

    conf = (params.w_tfidf * s_tfidf + params.w_concept * s_concept
            + params.w_entity * s_entity + params.w_event * same_event
            + params.w_time * s_time)
    if a.embed and b.embed:
        conf = (1 - params.embed_weight) * conf + params.embed_weight * s_embed

    reasons: list[str] = []
    if s_concept > 0.05:
        reasons.append("tema")
    if s_entity > 0.05:
        reasons.append("entidad")
    if s_tfidf >= params.tfidf_floor:
        reasons.append("texto")
    if s_embed >= 0.35:
        reasons.append("semántica")
    if same_event:
        reasons.append("evento")
    if s_time > 0:
        reasons.append("fecha")
    return min(conf, 1.0), reasons


def _cosine_list(a: list | None, b: list | None) -> float:
    if not a or not b:
        return 0.0
    return max(0.0, sum(x * y for x, y in zip(a, b)))   # vectores ya normalizados


# --------------------------------------------------------------------------- #
# Utilidades de cuerpo / front matter
# --------------------------------------------------------------------------- #
def _strip_relations_block(body: str) -> str:
    return _REL_BLOCK_RE.sub("", body).rstrip() + "\n"


def _clean_title(raw: str, stem: str) -> str:
    """Si el título es basura (p. ej. "£" de un OCR pobre), usa el nombre del archivo.

    Sólo afecta a cómo se MUESTRA la nota en enlaces y mapas; no se modifica el
    título guardado en su front matter.
    """
    raw = (raw or "").strip()
    return raw if sum(c.isalpha() for c in raw) >= 3 else stem


def _slug(s: str) -> str:
    s = normalize.strip_accents(str(s)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "x"


def _is_note(md: Path) -> bool:
    return (md.stem not in _INDEX_NAMES
            and not md.stem.startswith(_MOC_TEMA_PREFIX)
            and not md.stem.startswith("Mapa - ")
            and not md.name.startswith("_"))


_META_ORDER = ["title", "source", "file_type", "pages", "words", "ocr", "ocr_pages",
               "ocr_confidence", "language", "author", "date_processed", "aliases",
               "tags", "keywords", "conceptos", "entidades", "related"]


def _reorder_meta(meta: dict) -> dict:
    out = {k: meta[k] for k in _META_ORDER if k in meta}
    for k, v in meta.items():   # cualquier campo extra que no esté en el orden
        if k not in out:
            out[k] = v
    return out


# --------------------------------------------------------------------------- #
# Orquestador principal
# --------------------------------------------------------------------------- #
def relacionar_boveda(vault_dir, subdir: str = "PDF importados",
                      params: RelateParams | None = None, lex: Lexicon | None = None,
                      on_event=None) -> dict:
    """Detecta y escribe las relaciones entre las notas de la bóveda.

    Devuelve un resumen con contadores y la lista de relaciones (con confianza),
    útil para auditar (verificar que no hay relaciones falsas o excesivas).
    """
    params = params or RelateParams()
    lex = lex or Lexicon.load(params.lexicon_path)
    dest = Path(vault_dir) / subdir if subdir else Path(vault_dir)
    dest.mkdir(parents=True, exist_ok=True)

    notes = [md for md in sorted(dest.glob("*.md")) if _is_note(md)]
    idx_path = dest / "_semantica.json"
    cached = load_index(idx_path, lex)

    # 1) Perfilar (reutilizando lo que no cambió)
    profiles: dict[str, DocProfile] = {}
    parsed: dict[str, tuple[Path, dict, str]] = {}
    reused = 0
    for md in notes:
        text = md.read_text(encoding="utf-8")
        meta, body = split_front_matter(text)
        title = _clean_title(str(meta.get("title") or ""), md.stem)
        body_core = _strip_relations_block(body)
        h = content_hash(body_core)
        name = md.stem
        if name in cached and cached[name].content_hash == h:
            profiles[name] = cached[name]
            reused += 1
        else:
            profiles[name] = build_profile(name, title, body_core, lex)
        parsed[name] = (md, meta, body_core)
        if on_event:
            on_event("perfil", name)

    if not profiles:
        return {"total": 0, "relations": [], "links": 0, "temas": 0, "dest": str(dest)}

    # 2) Corpus + vectores
    live, edf, eidf = _build_corpus(profiles, params)

    # 2b) Embeddings opcionales
    if params.use_embeddings:
        from .embeddings import get_embedder
        emb = get_embedder(params.embed_model)
        if emb is not None:
            names = list(profiles)
            texts = [f"{profiles[n].title}. " + " ".join(profiles[n].keywords) for n in names]
            try:
                for n, v in zip(names, emb.embed(texts)):
                    live[n].embed = v
            except Exception:   # que un fallo del modelo no rompa el pipeline
                pass

    # 3) Puntuar todos los pares (una sola vez por par)
    names = list(profiles)
    pair_conf: dict[tuple[str, str], tuple[float, list[str]]] = {}
    all_relations: list[dict] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            conf, reasons = _confidence(live[a], live[b], params)
            if conf >= params.threshold:
                pair_conf[(a, b)] = (conf, reasons)
                all_relations.append({"a": a, "b": b, "confidence": round(conf, 3),
                                      "reasons": reasons})

    # 4) Adyacencia simétrica con tope top-K por nota
    adj: dict[str, list[tuple[str, float, list[str]]]] = defaultdict(list)
    for (a, b), (conf, reasons) in pair_conf.items():
        adj[a].append((b, conf, reasons))
        adj[b].append((a, conf, reasons))
    for name in adj:
        adj[name].sort(key=lambda x: -x[1])
        del adj[name][params.top_k:]

    # 5) Entidades "conectoras" (para tags entidad/…): compartidas y no genéricas
    n_docs = len(profiles)
    linkable_ents = {e for e, d in edf.items()
                     if d >= params.min_entity_df and d <= max(2, n_docs * params.max_entity_df_frac)}

    # 6) Escribir cada nota (sólo si cambió)
    written = 0
    for name, (md, meta, body_core) in parsed.items():
        prof = profiles[name]
        rels = adj.get(name, [])
        new_meta = _apply_metadata(meta, prof, rels, lex, params, linkable_ents)
        new_body = _apply_body(body_core, rels, profiles)
        content = render_front_matter(_reorder_meta(new_meta)) + "\n\n" + new_body.lstrip("\n")
        if not content.endswith("\n"):
            content += "\n"
        if content != md.read_text(encoding="utf-8"):
            md.write_text(content, encoding="utf-8")
            written += 1

    # 7) MOCs por tema + mapa de temas
    temas = _write_theme_mocs(dest, profiles, lex, params.concept_tag_min)

    # 8) Persistir índice + auditoría legible
    save_index(idx_path, profiles, all_relations, lex)
    _write_audit(dest, profiles, adj, params)

    return {
        "total": n_docs, "reused": reused, "written": written,
        "links": len(pair_conf), "relations": all_relations,
        "temas": len(temas), "dest": str(dest),
    }


# --------------------------------------------------------------------------- #
# Escritura de metadatos y cuerpo
# --------------------------------------------------------------------------- #
def _theme_tags(prof: DocProfile, lex: Lexicon, params: RelateParams) -> list[str]:
    tags: list[str] = []
    for cid, w in sorted(prof.concept_hits.items(), key=lambda x: -x[1]):
        if w < params.concept_tag_min:
            continue
        chain = lex.parents(cid)
        root = chain[-1] if chain else None
        if root and root != cid:
            tags.append(f"tema/{_slug(root)}")
            tags.append(f"tema/{_slug(root)}/{_slug(cid)}")
        else:
            tags.append(f"tema/{_slug(cid)}")
    # dedup preservando orden
    seen: set[str] = set()
    return [t for t in tags if not (t in seen or seen.add(t))]


def _apply_metadata(meta: dict, prof: DocProfile, rels, lex: Lexicon,
                    params: RelateParams, linkable_ents: set[str]) -> dict:
    meta = dict(meta)
    # tags: conservar los que no sean nuestros; recomponer tema/ evento/ entidad/
    base = [t for t in (meta.get("tags") or [])
            if not str(t).startswith(("tema/", "evento/", "entidad/"))]
    new_tags = list(base)
    for t in _theme_tags(prof, lex, params):
        if t not in new_tags:
            new_tags.append(t)
    if prof.event:
        et = f"evento/{_slug(prof.event)}"
        if et not in new_tags:
            new_tags.append(et)
    ent_keys = [e for e in prof.entities if e in linkable_ents]
    for e in ent_keys[:5]:
        et = f"entidad/{_slug(prof.entities_display.get(e, e))}"
        if et not in new_tags:
            new_tags.append(et)
    meta["tags"] = new_tags

    # keywords / conceptos / entidades (para el panel de Propiedades de Obsidian)
    if prof.keywords:
        meta["keywords"] = prof.keywords
    concept_labels = [lex.label(cid) for cid, w in
                      sorted(prof.concept_hits.items(), key=lambda x: -x[1])
                      if w >= params.concept_tag_min]
    if concept_labels:
        meta["conceptos"] = concept_labels
    ent_display = [prof.entities_display.get(e, e) for e in ent_keys[:8]]
    if ent_display:
        meta["entidades"] = ent_display
    else:
        meta.pop("entidades", None)

    # related: wikilinks en el front matter (para Propiedades y Graph View)
    if rels:
        meta["related"] = [f"[[{n}]]" for n, _c, _r in rels]
    else:
        meta.pop("related", None)
    return meta


def _apply_body(body_core: str, rels, profiles: dict[str, DocProfile]) -> str:
    body = _strip_relations_block(body_core).rstrip()
    if not rels:
        return body + "\n"
    lines = [body, "", "", _REL_START, "## 🔗 Notas relacionadas", "",
             "> Detectadas automáticamente. El porcentaje es el nivel de confianza.",
             ""]
    for other, conf, reasons in rels:
        title = profiles[other].title if other in profiles else other
        motivo = ", ".join(reasons) if reasons else "afinidad"
        lines.append(f"- {_wikilink(other, title)} — **{round(conf * 100)}%** · {motivo}")
    lines += ["", _REL_END, ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# MOCs por tema (nodos-hub del grafo por concepto)
# --------------------------------------------------------------------------- #
def _write_theme_mocs(dest: Path, profiles: dict[str, DocProfile], lex: Lexicon,
                      concept_min: float = 2.0) -> list[str]:
    # concepto → notas que lo tratan (con peso suficiente, para que el hub sea real)
    by_concept: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for name, p in profiles.items():
        for cid, w in p.concept_hits.items():
            if w >= concept_min:
                by_concept[cid].append((name, p.title))

    for viejo in dest.glob(f"{_MOC_TEMA_PREFIX}*.md"):   # limpiar ejecuciones previas
        viejo.unlink()

    created: list[tuple[str, str, int]] = []
    for cid, docs in by_concept.items():
        if len(docs) < 2:            # un tema con una sola nota no es un hub útil
            continue
        label = lex.label(cid)
        moc_name = slugify_filename(f"{_MOC_TEMA_PREFIX}{label}")
        chain = lex.parents(cid)
        root = chain[-1] if chain else cid
        tag = f"tema/{_slug(root)}/{_slug(cid)}" if chain else f"tema/{_slug(cid)}"
        items = sorted(set(docs), key=lambda x: x[1].lower())
        lines = [render_front_matter({"title": f"Tema — {label}", "tags": ["moc", tag]}),
                 "", f"# {label}", "", f"> {len(items)} nota(s) sobre este tema", ""]
        lines += [f"- {_wikilink(stem, title)}" for stem, title in items]
        lines.append("")
        (dest / f"{moc_name}.md").write_text("\n".join(lines), encoding="utf-8")
        created.append((moc_name, label, len(items)))

    # Mapa de Temas: hub de hubs (no toca el Índice por formato, que es de organizar)
    if created:
        lines = [render_front_matter({"title": "Mapa de Temas", "tags": ["moc", "índice"]}),
                 "", "# Mapa de Temas", "",
                 f"> {len(created)} tema(s) · actualizado {date.today().isoformat()}", ""]
        for moc_name, label, n in sorted(created, key=lambda x: (-x[2], x[1].lower())):
            lines.append(f"- [[{moc_name}|{label}]] ({n})")
        lines.append("")
        (dest / f"{_MAPA_TEMAS}.md").write_text("\n".join(lines), encoding="utf-8")
    else:
        (dest / f"{_MAPA_TEMAS}.md").unlink(missing_ok=True)

    return [c[0] for c in created]


# --------------------------------------------------------------------------- #
# Auditoría legible (para verificar que no hay relaciones falsas/excesivas)
# --------------------------------------------------------------------------- #
def _write_audit(dest: Path, profiles: dict[str, DocProfile], adj, params: RelateParams) -> None:
    lines = ["# Auditoría de relaciones (archivo de sistema)", "",
             f"Umbral de confianza: **{round(params.threshold * 100)}%** · "
             f"máx. {params.top_k} por nota · {len(profiles)} notas.", ""]
    for name in sorted(profiles):
        p = profiles[name]
        rels = adj.get(name, [])
        lines.append(f"## {p.title}")
        meta_bits = []
        if p.concept_hits:
            meta_bits.append("conceptos: " + ", ".join(sorted(p.concept_hits)))
        if p.event:
            meta_bits.append(f"evento: {p.event}")
        if meta_bits:
            lines.append("_" + " · ".join(meta_bits) + "_")
        if rels:
            for other, conf, reasons in rels:
                t = profiles[other].title if other in profiles else other
                lines.append(f"- {round(conf * 100)}%  {t}  ({', '.join(reasons)})")
        else:
            lines.append("- (sin relaciones sobre el umbral)")
        lines.append("")
    (dest / "_relaciones.md").write_text("\n".join(lines), encoding="utf-8")
