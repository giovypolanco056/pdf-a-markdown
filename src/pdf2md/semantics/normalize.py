"""Normalización de texto en español para el análisis semántico.

Todo el motor compara texto ya normalizado: en minúsculas, sin acentos, sin
palabras vacías (stopwords) y con un *stemming* ligero que une singular/plural
y unas pocas terminaciones frecuentes. Lo importante es que TANTO el texto de
las notas COMO los términos del léxico pasen por las mismas funciones de aquí,
para que la comparación sea coherente.

Sólo usa la librería estándar (re, unicodedata).
"""
from __future__ import annotations

import re
import unicodedata

_VOWELS = set("aeiou")

# Palabras vacías del español (artículos, preposiciones, conjunciones, muletillas
# de documentos administrativos…). Se amplía sin problema; de más es inofensivo.
STOPWORDS: frozenset[str] = frozenset("""
a al algo alguna algunas alguno algunos ante antes aquel aquella aquellas aquello
aquellos aqui asi aun aunque bajo bien cada casi como con contra cual cuales
cualquier cuando cuanta cuantas cuanto cuantos de del demas desde donde dos e el
ella ellas ello ellos en entre era erais eran eras eres es esa esas ese eso esos
esta estaba estaban estamos estan estar estas este esto estos estoy fin fue fueron
fui fuimos ha habia habian han hasta hay he hemos hoy la las le les lo los mas me
mediante mi mientras mis misma mismas mismo mismos mucha muchas mucho muchos muy
nada ni no nos nosotros nuestra nuestras nuestro nuestros o os otra otras otro otros
para pero poca pocas poco pocos por porque pous que quien quienes se sea sean segun
ser si sido siempre sin sobre solo somos son soy su sus tal tambien tampoco tan
tanta tantas tanto tantos te tenemos tener tengo ti tiene tienen toda todas todo
todos tras tu tus un una unas uno unos usted ustedes va vamos van varias varios ver
vez y ya yo cabe cada
etc mismo cual dicho dicha dichos dichas ademas asimismo entonces luego pues
través traves cuyo cuya cuyos cuyas sino aquel esa este
""".split())

# Palabras muy comunes en documentos que rara vez ayudan a distinguir un tema.
STOPWORDS = STOPWORDS | frozenset("""
documento documentos pagina paginas señor señora fecha numero num art articulo
articulos punto puntos parte partes caso casos ano años dia dias mes meses
señores don doña sr sra ing lic dr dra
""".split())

# Verbos y muletillas de relleno (no distinguen el tema; ensucian los keywords).
STOPWORDS = STOPWORDS | frozenset("""
presente presenta presentan contempla contemplan incluye incluyen incluir abarca
permite permiten permitir señala señalan indica indican realiza realizan realizar
consiste corresponde correspondiente respecto dado dada dados dadas cabe cuenta
tanto tal manera modo forma siguiente siguientes mismo debe deben debera hacer
existe existen tiene tienen puede pueden podra podran ser estar haber
""".split())

_WORD_RE = re.compile(r"[a-záéíóúñü]{2,}", re.IGNORECASE)


def strip_accents(text: str) -> str:
    """Quita acentos y diéresis (á→a, ü→u) manteniendo la ñ→n."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def stem(word: str) -> str:
    """*Stemming* ligero y conservador para español (ya en minúsculas, sin acentos).

    Une plurales y unas pocas terminaciones. Es deliberadamente prudente: es peor
    fusionar de más (baja la precisión) que dejar un plural suelto (baja un poco
    la exhaustividad, que otras señales compensan).
    """
    w = word
    if len(w) <= 4:
        return w
    # nominalizaciones frecuentes → raíz común
    for suf in ("amiento", "imiento", "aciones", "iciones", "acion", "icion",
                "adora", "adoras", "ancia", "encia"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    # plurales
    if w.endswith("ces"):           # luces→luz, capaces→capaz
        return w[:-3] + "z"
    if w.endswith("es") and len(w) > 4 and w[-3] not in _VOWELS:
        return w[:-2]               # centrales→central, reuniones→reunion
    if w.endswith("s") and len(w) > 3 and w[-2] in _VOWELS:
        return w[:-1]               # proyectos→proyecto, notas→nota
    return w


def token_pairs(text: str, *, keep_stopwords: bool = False) -> list[tuple[str, str]]:
    """Como `tokens`, pero devuelve pares (raíz, forma_original_sin_acentos).

    La forma original sirve para mostrar keywords legibles ("almacenamiento" en
    vez de la raíz "almacen") sin perder la fusión que hace el stemming.
    """
    out: list[tuple[str, str]] = []
    for m in _WORD_RE.finditer(text):
        raw = strip_accents(m.group(0).lower())
        if not keep_stopwords and raw in STOPWORDS:
            continue
        st = stem(raw)
        if len(st) < 3:
            continue
        if not keep_stopwords and st in STOPWORDS:
            continue
        out.append((st, raw))
    return out


def tokens(text: str, *, keep_stopwords: bool = False, do_stem: bool = True) -> list[str]:
    """Convierte texto libre en una lista de tokens normalizados.

    minúsculas → sin acentos → sólo palabras (≥2 letras) → sin stopwords → stem.
    """
    if do_stem:
        return [st for st, _ in token_pairs(text, keep_stopwords=keep_stopwords)]
    out: list[str] = []
    for m in _WORD_RE.finditer(text):
        w = strip_accents(m.group(0).lower())
        if len(w) < 3:
            continue
        if not keep_stopwords and w in STOPWORDS:
            continue
        out.append(w)
    return out


def term_tuple(term: str) -> tuple[str, ...]:
    """Normaliza un término del léxico (posiblemente multi-palabra) a una tupla
    de tokens, lista para buscarla dentro del flujo de tokens de una nota."""
    return tuple(tokens(term))


def ngrams(seq: list[str], n: int) -> list[tuple[str, ...]]:
    """n-gramas contiguos de una lista de tokens."""
    if n <= 1:
        return [(t,) for t in seq]
    return [tuple(seq[i : i + n]) for i in range(len(seq) - n + 1)]
