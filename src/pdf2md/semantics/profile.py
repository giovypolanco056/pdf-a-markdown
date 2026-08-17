"""Perfil semántico de cada nota + índice auxiliar incremental.

Un `DocProfile` resume todo lo que el motor necesita saber de una nota: sus
términos (para TF-IDF), los conceptos y el evento detectados, sus entidades y su
fecha. Los perfiles se guardan en un índice JSON (`_semantica.json`) junto a un
hash del contenido, de modo que al re-ejecutar sólo se re-analizan las notas que
cambiaron (respuesta a "cómo mantener el sistema actualizado al agregar notas").
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import entities as ent
from . import normalize
from .lexicon import Lexicon

_INDEX_VERSION = 3
# Súbelo si cambia la lógica de análisis (build_profile). Junto con la huella del
# léxico, decide si los perfiles cacheados siguen siendo válidos.
ANALYZER_VERSION = "4"
_NAME_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DMY = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_PAGE_MARK = re.compile(r"<!--\s*página\s+\d+\s*-->")


@dataclass
class DocProfile:
    name: str
    title: str
    content_hash: str
    tf: dict[str, int] = field(default_factory=dict)
    concept_hits: dict[str, float] = field(default_factory=dict)
    concept_vec: dict[str, float] = field(default_factory=dict)
    event: str | None = None
    entities: dict[str, str] = field(default_factory=dict)   # key -> kind
    entities_display: dict[str, str] = field(default_factory=dict)  # key -> texto legible
    surface: dict[str, str] = field(default_factory=dict)    # raíz -> forma legible
    doc_date: str | None = None       # fecha del documento (no de proceso)
    n_tokens: int = 0
    keywords: list[str] = field(default_factory=list)   # se rellena con el corpus
    tfidf: dict[str, float] = field(default_factory=dict)  # idem

    # -------------------------------------------------- serialización JSON
    def to_json(self) -> dict:
        return {
            "name": self.name, "title": self.title, "content_hash": self.content_hash,
            "tf": self.tf, "concept_hits": self.concept_hits, "event": self.event,
            "entities": self.entities, "entities_display": self.entities_display,
            "surface": self.surface,
            "doc_date": self.doc_date, "n_tokens": self.n_tokens,
            "keywords": self.keywords,
        }

    @classmethod
    def from_json(cls, d: dict, lex: Lexicon) -> "DocProfile":
        p = cls(name=d["name"], title=d.get("title", d["name"]),
                content_hash=d.get("content_hash", ""),
                tf={k: int(v) for k, v in (d.get("tf") or {}).items()},
                concept_hits={k: float(v) for k, v in (d.get("concept_hits") or {}).items()},
                event=d.get("event"), entities=d.get("entities") or {},
                entities_display=d.get("entities_display") or {},
                surface=d.get("surface") or {},
                doc_date=d.get("doc_date"), n_tokens=int(d.get("n_tokens", 0)),
                keywords=d.get("keywords") or [])
        p.concept_vec = lex.expand_parents(Counter(p.concept_hits))
        return p


def content_hash(body: str) -> str:
    return hashlib.sha1(body.encode("utf-8", "ignore")).hexdigest()[:16]


def _doc_date(name: str, text: str) -> str | None:
    """Fecha del documento: primero del nombre (2026-08-01-...), luego del texto.

    Se usa la fecha del *documento*, no la de conversión (que sería igual para
    todo lo procesado el mismo día y dispararía falsas relaciones temporales).
    """
    m = _NAME_DATE.search(name)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass
    m = _DMY.search(text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            pass
    return None


def build_profile(name: str, title: str, body: str, lex: Lexicon) -> DocProfile:
    """Construye el perfil de una nota a partir de su título y cuerpo (sin front matter).

    ``body`` es el cuerpo canónico (sin nuestra sección de relaciones). El hash se
    calcula sobre él tal cual; las marcas de página se quitan sólo para analizar.
    """
    # El título es muy informativo: se repite para que pese más en el análisis.
    analysis = (title + ". ") * 3 + _PAGE_MARK.sub(" ", body)
    pairs = normalize.token_pairs(analysis)
    toks = [st for st, _ in pairs]
    # raíz → forma legible más frecuente (para keywords bonitos)
    sf: dict[str, Counter] = {}
    for st, raw in pairs:
        sf.setdefault(st, Counter())[raw] += 1
    surface = {st: c.most_common(1)[0][0] for st, c in sf.items()}

    hits = lex.detect_concepts(toks)
    event, _ = lex.detect_event(toks)
    ents = ent.extract(title + "\n" + body)

    prof = DocProfile(
        name=name, title=title, content_hash=content_hash(body),
        tf=dict(Counter(toks)),
        concept_hits={k: float(v) for k, v in hits.items()},
        concept_vec=lex.expand_parents(hits),
        event=event,
        entities={e.key: e.kind for e in ents},
        entities_display={e.key: e.display for e in ents},
        surface=surface,
        doc_date=_doc_date(name, body),
        n_tokens=len(toks),
    )
    return prof


# --------------------------------------------------------------------------- #
# Índice auxiliar persistente
# --------------------------------------------------------------------------- #
def analyzer_signature(lex: Lexicon) -> str:
    """Huella que invalida la caché cuando cambia el léxico o la lógica de análisis."""
    return f"{ANALYZER_VERSION}:{lex.sig}"


def load_index(path: Path, lex: Lexicon) -> dict[str, DocProfile]:
    """Carga los perfiles guardados (para reutilizar los que no cambiaron).

    Si el formato, la lógica de análisis o el léxico cambiaron, devuelve vacío
    para forzar un re-análisis completo (así, editar `conceptos.yaml` recalcula todo).
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if data.get("version") != _INDEX_VERSION or data.get("analyzer") != analyzer_signature(lex):
        return {}   # formato/léxico/lógica cambiaron: se reconstruye entero
    out: dict[str, DocProfile] = {}
    for d in data.get("docs", []):
        try:
            p = DocProfile.from_json(d, lex)
            out[p.name] = p
        except (KeyError, TypeError):
            continue
    return out


def save_index(path: Path, profiles: dict[str, DocProfile], relations: list[dict],
               lex: Lexicon | None = None) -> None:
    payload = {
        "version": _INDEX_VERSION,
        "analyzer": analyzer_signature(lex) if lex is not None else None,
        "updated": date.today().isoformat(),
        "docs": [p.to_json() for p in profiles.values()],
        "relations": relations,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
