"""Pruebas de la capa semántica (relaciones entre notas). NO requiere red ni deps pesadas.

Ejecutar:  python -m pytest tests/test_semantics.py -v
           o directamente:  python tests/test_semantics.py

Verifica lo esencial que pidió el proyecto:
  * el puente por concepto padre relaciona notas que NO comparten palabras,
  * una nota fuera de tema (control) NO se relaciona (precisión > cantidad),
  * los mapas por tema y la sección de relaciones se generan,
  * el proceso es idempotente e incremental.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pdf2md.semantics import entities, normalize
from pdf2md.semantics.lexicon import Lexicon
from pdf2md.semantics.relate import RelateParams, relacionar_boveda


# --------------------------------------------------------------------------- #
# Fixtures de notas (mínimas pero realistas). Cada una imita la salida del
# conversor: front matter + marca de página + cuerpo.
# --------------------------------------------------------------------------- #
_NOTES = {
    # Sólo concepto "energia" (reunión). No dice "hidrobombeo" ni "almacenamiento".
    "2026-08-03-Reunion-Energia": ("Reunión sobre planificación energética",
        "Minuta de la reunión sobre la matriz energética y la generación "
        "eléctrica del sistema. Se acordó dar seguimiento en la convocatoria."),
    # Sólo concepto "almacenamiento-energetico". No dice "energía" a secas ni "bombeo".
    "2026-08-07-Almacenamiento-Energetico": ("Almacenamiento energético mediante agua",
        "El almacenamiento energético mediante agua sirve de reserva energética; "
        "guarda energia en horas valle y la devuelve en horas pico."),
    # Concepto "hidrobombeo" (+ padres). Comparte entidad EGEHID con el informe.
    "2026-08-01-Proyecto-Hidrobombeo": ("Proyecto de Hidrobombeo Valle Nuevo",
        "Proyecto de una central de hidrobombeo impulsado por EGEHID, con embalse "
        "superior e inferior y turbinas reversibles. Cronograma en tres fases."),
    "2026-08-10-Informe-Proyecto": ("Informe de avance del proyecto",
        "Informe de avance del proyecto de hidrobombeo de EGEHID. La central "
        "reversible avanza según el cronograma. Conclusiones y recomendaciones."),
    # CONTROL: recursos humanos, sin relación con energía. No debe enlazarse.
    "2026-08-09-Solicitud-Vacaciones": ("Solicitud de vacaciones del personal",
        "Formulario de solicitud de vacaciones al departamento de recursos "
        "humanos. Se pide el permiso laboral y actualizar la nómina del personal."),
}


def _make_vault(root: Path) -> Path:
    sub = root / "PDF importados"
    sub.mkdir(parents=True, exist_ok=True)
    for name, (title, body) in _NOTES.items():
        fm = (f'---\ntitle: "{title}"\nsource: "{name}.pdf"\nfile_type: "pdf"\n'
              f'language: "es"\ntags:\n  - "pdf-importado"\n  - "origen/pdf"\n---\n\n')
        (sub / f"{name}.md").write_text(fm + "<!-- página 1 -->\n" + body + "\n",
                                        encoding="utf-8")
    return root


# --------------------------------------------------------------------------- #
def test_normalize_stem():
    assert normalize.stem("centrales") == "central"
    assert normalize.stem("proyectos") == "proyecto"
    assert normalize.stem("reuniones") == "reunion"
    toks = normalize.tokens("El proyecto de la central")   # 'el','de','la' son stopwords
    assert "proyecto" in toks and "central" in toks
    assert "el" not in toks and "de" not in toks
    print("[OK] normalización: stemming + stopwords")


def test_lexicon_parent_bridge():
    """Dos notas que sólo comparten el ANCESTRO común deben solaparse en él."""
    lex = Lexicon.load()
    assert lex.concepts, "el léxico de serie debe cargar"
    t_reunion = normalize.tokens("matriz energética y generación eléctrica")
    t_almac = normalize.tokens("almacenamiento energético mediante agua, reserva energética")
    v1 = lex.expand_parents(lex.detect_concepts(t_reunion))
    v2 = lex.expand_parents(lex.detect_concepts(t_almac))
    # Ambos deben tener peso en 'energia' aunque activen conceptos distintos
    assert v1.get("energia", 0) > 0 and v2.get("energia", 0) > 0
    print("[OK] puente semántico por concepto padre (energia)")


def test_entities():
    ents = {e.key: e.kind for e in entities.extract(
        "El Decreto 230-18 y EGEHID el 12 de agosto de 2024.")}
    assert any(k == "230-18" for k in ents)          # código
    assert "egehid" in ents and ents["egehid"] == "sigla"
    assert any(v == "fecha" for v in ents.values())  # fecha
    print("[OK] extracción de entidades: sigla + código + fecha")


def test_relate_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(Path(tmp))
        params = RelateParams()
        s1 = relacionar_boveda(vault, "PDF importados", params=params)

        rels = {(min(r["a"], r["b"]), max(r["a"], r["b"])) for r in s1["relations"]}
        names = {n: n for n in _NOTES}

        # 1) El control (RRHH) no se relaciona con NADA (precisión)
        control = "2026-08-09-Solicitud-Vacaciones"
        assert not any(control in pair for pair in rels), \
            "la nota de control no debería tener relaciones"

        # 2) El puente: Reunión(energia) ↔ Almacenamiento(almacenamiento-energetico)
        bridge = tuple(sorted(("2026-08-03-Reunion-Energia",
                               "2026-08-07-Almacenamiento-Energetico")))
        assert bridge in rels, "las dos notas energéticas deben relacionarse vía el padre"

        # 3) Proyecto ↔ Informe (tema + entidad compartida) es la relación más fuerte
        strong = tuple(sorted(("2026-08-01-Proyecto-Hidrobombeo",
                               "2026-08-10-Informe-Proyecto")))
        assert strong in rels

        # 4) Se crearon mapas por tema
        sub = vault / "PDF importados"
        assert list(sub.glob("Tema - *.md")), "deben crearse MOCs por tema"
        assert (sub / "Mapa de Temas.md").exists()

        # 5) Las notas energéticas tienen la sección de relaciones; el control no
        energetica = (sub / "2026-08-01-Proyecto-Hidrobombeo.md").read_text(encoding="utf-8")
        assert "🔗 Notas relacionadas" in energetica
        control_txt = (sub / f"{control}.md").read_text(encoding="utf-8")
        assert "🔗 Notas relacionadas" not in control_txt

        # 6) Idempotencia + incremental: 2ª pasada no reescribe y reutiliza todo
        s2 = relacionar_boveda(vault, "PDF importados", params=params)
        assert s2["written"] == 0, "una 2ª pasada sin cambios no debe reescribir"
        assert s2["reused"] == len(_NOTES), "debe reutilizar todos los perfiles del índice"

    print("[OK] relaciones de punta a punta: puente, precisión, MOCs, idempotencia")


if __name__ == "__main__":
    test_normalize_stem()
    test_lexicon_parent_bridge()
    test_entities()
    test_relate_end_to_end()
    print("\nTodas las pruebas de la capa semántica pasaron.")
