"""Léxico de conceptos y tipos de evento (conocimiento del dominio, editable).

El léxico es la pieza que aporta *significado* sin necesidad de un modelo de
lenguaje: agrupa términos equivalentes bajo un mismo **concepto** y organiza los
conceptos en una **jerarquía** (cada concepto puede tener un `padre`).

Ejemplo del porqué de la jerarquía:

    hidrobombeo            (padre: energia)
    almacenamiento-energetico (padre: energia)

Dos notas —una que sólo dice "planta de bombeo" y otra que sólo dice
"almacenamiento energético mediante agua"— activan conceptos DISTINTOS, pero
ambos cuelgan del padre `energia`. Al puntuar la similitud, cada concepto
"irradia" peso hacia sus padres, de modo que las dos notas se encuentran en el
nodo `energia` aunque no compartan ni una palabra. Ése es el puente semántico.

El contenido vive en `data/conceptos.yaml`; este módulo sólo lo carga y lo
consulta. Añadir dominios = editar ese YAML (datos, no código).
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import normalize

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_DATA_DIR = Path(__file__).parent / "data"
_DEFAULT_FILE = _DATA_DIR / "conceptos.yaml"


@dataclass
class Concept:
    cid: str
    label: str
    parent: str | None = None
    # términos ya normalizados a tuplas de tokens, agrupados por su longitud
    terms_by_len: dict[int, set[tuple[str, ...]]] = field(default_factory=dict)


@dataclass
class Lexicon:
    concepts: dict[str, Concept] = field(default_factory=dict)
    events: dict[str, dict[int, set[tuple[str, ...]]]] = field(default_factory=dict)
    sig: str = "nofile"   # huella del contenido del léxico (invalida la caché al cambiar)
    _unigram_index: dict[str, list[str]] = field(default_factory=dict)  # token → cids
    _max_term_len: int = 1

    # ------------------------------------------------------------------ carga
    @classmethod
    def load(cls, path: str | Path | None = None) -> "Lexicon":
        lex = cls()
        p = Path(path) if path else _DEFAULT_FILE
        if yaml is None or not p.exists():
            return lex
        text = p.read_text(encoding="utf-8")
        lex.sig = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
        data = yaml.safe_load(text) or {}

        for cid, spec in (data.get("conceptos") or {}).items():
            spec = spec or {}
            concept = Concept(cid=cid,
                              label=str(spec.get("label", cid)),
                              parent=spec.get("padre") or spec.get("parent"))
            for term in spec.get("terminos", []) or []:
                tup = normalize.term_tuple(str(term))
                if tup:
                    concept.terms_by_len.setdefault(len(tup), set()).add(tup)
                    lex._max_term_len = max(lex._max_term_len, len(tup))
            lex.concepts[cid] = concept
            # índice inverso de unigramas para un primer barrido rápido
            for tup in concept.terms_by_len.get(1, ()):  # type: ignore[union-attr]
                lex._unigram_index.setdefault(tup[0], []).append(cid)

        for eid, spec in (data.get("eventos") or {}).items():
            spec = spec or {}
            by_len: dict[int, set[tuple[str, ...]]] = {}
            for term in spec.get("terminos", []) or []:
                tup = normalize.term_tuple(str(term))
                if tup:
                    by_len.setdefault(len(tup), set()).add(tup)
                    lex._max_term_len = max(lex._max_term_len, len(tup))
            lex.events[eid] = by_len
        return lex

    # ------------------------------------------------------------- consultas
    def detect_concepts(self, toks: list[str]) -> Counter:
        """Cuenta cuántas veces aparece cada concepto en el flujo de tokens.

        Devuelve un Counter {concept_id: nº de coincidencias} (sólo del concepto
        directo; la irradiación al padre la hace `expand_parents`).
        """
        hits: Counter = Counter()
        token_set = set(toks)
        # 1) unigramas: barrido O(1) por el índice inverso
        for cid in {c for t in token_set for c in self._unigram_index.get(t, ())}:
            concept = self.concepts[cid]
            for tup in concept.terms_by_len.get(1, ()):  # type: ignore[union-attr]
                if tup[0] in token_set:
                    hits[cid] += toks.count(tup[0])
        # 2) términos multi-palabra: ventana deslizante. Una frase pesa MÁS que
        #    una palabra suelta (una coincidencia de 2 palabras vale 2, etc.):
        #    es más distintiva y da mucha más precisión que un término genérico.
        for n in range(2, self._max_term_len + 1):
            windows = Counter(normalize.ngrams(toks, n))
            if not windows:
                continue
            for cid, concept in self.concepts.items():
                for tup in concept.terms_by_len.get(n, ()):  # type: ignore[union-attr]
                    c = windows.get(tup, 0)
                    if c:
                        hits[cid] += c * n
        return hits

    def detect_event(self, toks: list[str]) -> tuple[str | None, dict[str, int]]:
        """Clasifica el tipo de evento dominante (reunión, informe, incidente…).

        Devuelve (tipo o None, puntuaciones por tipo). El None es importante: si
        no hay señales claras, no se fuerza una etiqueta.
        """
        token_set = set(toks)
        scores: dict[str, int] = {}
        bigrams = Counter(normalize.ngrams(toks, 2)) if toks else Counter()
        for eid, by_len in self.events.items():
            s = 0
            for tup in by_len.get(1, ()):
                if tup[0] in token_set:
                    s += toks.count(tup[0])
            for tup in by_len.get(2, ()):
                s += bigrams.get(tup, 0)
            if s:
                scores[eid] = s
        if not scores:
            return None, {}
        best = max(scores, key=lambda k: scores[k])
        return best, scores

    def parents(self, cid: str) -> list[str]:
        """Cadena de padres de un concepto (del más cercano al más lejano)."""
        chain: list[str] = []
        seen = {cid}
        cur = self.concepts.get(cid)
        while cur and cur.parent and cur.parent not in seen:
            chain.append(cur.parent)
            seen.add(cur.parent)
            cur = self.concepts.get(cur.parent)
        return chain

    def label(self, cid: str) -> str:
        c = self.concepts.get(cid)
        return c.label if c else cid

    def expand_parents(self, hits: Counter, alpha: float = 0.5) -> dict[str, float]:
        """Irradia el peso de cada concepto hacia sus padres (el puente semántico).

        Un concepto con peso ``w`` suma ``w`` a sí mismo y ``alpha**k · w`` a su
        padre de nivel k. Así, conceptos hermanos se solapan en el ancestro común.
        """
        vec: dict[str, float] = {}
        for cid, w in hits.items():
            vec[cid] = vec.get(cid, 0.0) + float(w)
            for k, pid in enumerate(self.parents(cid), start=1):
                vec[pid] = vec.get(pid, 0.0) + (alpha ** k) * float(w)
        return vec
