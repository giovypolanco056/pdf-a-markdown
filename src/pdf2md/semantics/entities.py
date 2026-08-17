"""Extracción de entidades del texto (personas, organizaciones, siglas, fechas…).

Para relacionar documentos, las entidades COMPARTIDAS son una señal de alta
precisión: si dos notas mencionan "EGEHID" o "Decreto 230-18", probablemente
hablan de lo mismo. No se pretende una clasificación perfecta persona/empresa
(eso exigiría un modelo de NER); basta con capturar cadenas distintivas y una
categoría aproximada, y luego premiar las que dos notas tengan en común.

Se trabaja sobre el texto ORIGINAL (con mayúsculas y acentos) porque la
capitalización es la principal pista. Sólo librería estándar (re).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from . import normalize

# --- Patrones ---------------------------------------------------------------
# Siglas: 2-8 mayúsculas seguidas (EGEHID, PLERD, NIC, MONUDIS, ENCS, MUN…).
_ACRONYM = re.compile(r"\b([A-ZÁÉÍÓÚÑ]{2,8})\b")

# Códigos/expedientes/normas: AC-2025-0017, 230-18, núm. 313-22, RD-2024…
_CODE = re.compile(r"\b([A-Za-zÁÉÍÓÚÑ]{0,4}-?\d{2,4}(?:-\d{1,4})+)\b")

# Fechas: 12/08/2026, 2026-08-12, "12 de agosto de 2026".
_MESES = ("enero febrero marzo abril mayo junio julio agosto septiembre setiembre "
          "octubre noviembre diciembre").split()
_DATE_NUM = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")
_DATE_TXT = re.compile(r"\b(\d{1,2})\s+de\s+(" + "|".join(_MESES) + r")(?:\s+de\s+(\d{4}))?",
                       re.IGNORECASE)

# Nombres propios: 2-4 palabras capitalizadas seguidas (con conectores de/del/la).
_PROPER = re.compile(
    r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñü]{2,}(?:\s+(?:de|del|la|las|los|y|e)\s+|\s+)"
    r"[A-ZÁÉÍÓÚÑ][a-záéíóúñü]{2,}(?:(?:\s+(?:de|del|la|las|los|y|e)\s+|\s+)"
    r"[A-ZÁÉÍÓÚÑ][a-záéíóúñü]{2,}){0,2})\b")

# Palabras que, aunque vayan capitalizadas (inicio de frase, títulos), no son
# entidades. Se comparan sin acentos y en minúsculas.
_PROPER_STOP = frozenset(normalize.strip_accents(w) for w in """
el la los las un una este esta ese esa aquel para por con sin sobre entre desde
presentacion introduccion conclusion conclusiones resumen indice anexo capitulo
seccion articulo decreto ley considerando resultando por tanto no obstante
ademas asimismo objetivo objetivos alcance nota informe reunion acta segun
""".lower().split())

# Siglas demasiado genéricas o ruido de OCR que no aportan.
_ACRONYM_STOP = frozenset("""
PDF ID II III IV VI VII VIII IX XI XII XX EL LA LOS SI NO SE DE POR OK IE OACI ONU
""".split())


@dataclass(frozen=True)
class Entity:
    key: str      # forma canónica normalizada (para comparar entre notas)
    display: str  # forma legible (como apareció)
    kind: str     # sigla | codigo | fecha | nombre


def _norm_key(s: str) -> str:
    return re.sub(r"\s+", " ", normalize.strip_accents(s).lower()).strip()


def extract(text: str, *, max_entities: int = 40) -> list[Entity]:
    """Devuelve las entidades más relevantes del texto (deduplicadas)."""
    found: dict[str, Entity] = {}
    freq: Counter = Counter()

    def add(display: str, kind: str) -> None:
        display = display.strip(" .,:;")
        key = _norm_key(display)
        if not key or len(key) < 2:
            return
        freq[key] += 1
        if key not in found:
            found[key] = Entity(key=key, display=display, kind=kind)

    for m in _ACRONYM.finditer(text):
        sig = m.group(1)
        if sig in _ACRONYM_STOP or sig.title() in _PROPER_STOP:
            continue
        # En documentos OCR en MAYÚSCULAS, palabras corrientes ("DEL", "QUE",
        # "CON"…) parecen siglas. Se descartan si en minúscula son stopwords.
        if normalize.strip_accents(sig.lower()) in normalize.STOPWORDS:
            continue
        add(sig, "sigla")

    for m in _CODE.finditer(text):
        add(m.group(1), "codigo")

    for m in _DATE_NUM.finditer(text):
        add(m.group(1), "fecha")
    for m in _DATE_TXT.finditer(text):
        add(m.group(0), "fecha")

    for m in _PROPER.finditer(text):
        phrase = m.group(1)
        first = normalize.strip_accents(phrase.split()[0].lower())
        if first in _PROPER_STOP:
            continue
        add(phrase, "nombre")

    # ordena por frecuencia (las más repetidas suelen ser las más relevantes)
    ordered = sorted(found.values(), key=lambda e: (-freq[e.key], e.kind, e.key))
    return ordered[:max_entities]
