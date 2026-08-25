# Roadmap — PDF → Markdown (sistema RAG por etapas)

Plan de evolución del proyecto. La **Fase 1** (conversión PDF → Markdown) está
completa; este documento ordena las mejoras siguientes por **impacto** y
**esfuerzo**, manteniendo la prioridad del proyecto: *primero la calidad de la
conversión, porque de ella depende todo el RAG posterior.*

## Cómo leer este roadmap

- **Impacto / Esfuerzo:** `Alto` · `Medio` · `Bajo`.
- **⭐** = recomendado hacer pronto (buena relación impacto/esfuerzo).
- Las fases 2–4 corresponden a la visión original (Obsidian → indexación → RAG).

---

## ✅ Estado actual (Fase 1, hecho)

- Conversión de PDF **digitales** y **escaneados** (OCR Tesseract, español).
- **Word (.docx) y Excel (.xlsx)** además de PDF: un lector por formato
  (`docx_extractor`, `xlsx_extractor`) tras un despachador común (`convert_file`),
  con la misma salida Markdown. Word mapea títulos/listas/tablas; Excel vuelca
  cada hoja como tabla.
- Detección automática digital vs. escaneado, por página.
- Extracción de títulos, listas, párrafos y **tablas con líneas**.
- Limpieza de OCR (sin inventar) y avisos de baja confianza.
- Metadatos YAML + marcas de página `<!-- página N -->` (trazabilidad para RAG).
- Tres formas de uso: **CLI** (`main.py`), **interfaz gráfica** (`gui.py`) y
  **modo vigilancia** (`watch.py`, carpeta que se auto-convierte).
- Manejo de errores por lotes y estructura preparada para RAG (`src/pdf2md/rag/`).

---

## Fase 1.5 — Calidad de conversión (corto plazo)

> El mayor retorno para el RAG. Ataca los fallos reales vistos en documentos de prueba.

| Mejora | Impacto | Esfuerzo | Notas |
|---|---|---|---|
| ⭐ **Tablas sin bordes** | Alto | Medio | Respaldo con **pdfplumber** (estrategia por texto) o Camelot cuando PyMuPDF no halla líneas. Arregla facturas. |
| ⭐ **Preprocesado de imagen (OCR)** | Alto | Medio | Deskew + binarización + quitar ruido (Pillow/OpenCV) antes de Tesseract. Mejora escaneos torcidos o pobres. |
| **Detección de títulos más fina** | Medio | Bajo | Usar centrado y patrones de numeración; evitar que firmas/negritas salgan como `###`. |
| **Corrección OCR opcional (ES)** | Medio | Bajo | `pyspellchecker`; **marcar** dudas, no inventarlas. Activable por config. |
| **Detección automática de idioma** | Medio | Bajo | `langdetect` para elegir modelo OCR y el metadato `language`. |
| **Motor alternativo (difíciles)** | Alto | Alto | **Docling** / **Marker** detrás de la misma interfaz para maquetación compleja o multicolumna. |

---

## Fase 1.6 — Robustez y empaquetado

> Para que el proyecto sea fiable y fácil de instalar/mantener.

| Mejora | Impacto | Esfuerzo | Notas |
|---|---|---|---|
| ⭐ **Pruebas reales (pytest)** | Alto | Medio | PDFs de muestra (digital, escaneado, tabla, cifrado, corrupto) y verificar la salida. Hoy solo hay *smoke tests*. |
| **CI en GitHub Actions** | Medio | Bajo | Tests + `ruff` (linter) + `mypy` (tipos) en cada push. |
| **`pyproject.toml`** | Medio | Bajo | Instalar como paquete (`pip install -e .`) y comando global `pdf2md`. |
| **Ejecutable `.exe`** | Medio | Medio | **PyInstaller** para no depender de instalar Python. |
| **Paralelismo en lotes** | Medio | Medio | `multiprocessing` para convertir varios PDF a la vez. |
| **Log a archivo** | Bajo | Bajo | Registro con rotación, además de la consola. |

---

## Fase 2 — Organización / Obsidian

> Convertir la carpeta de Markdown en una base de conocimiento navegable.

> ✅ **Hecho (2026-08-12):** publicación a la bóveda con `publicar.py` /
> `publicar.bat` (módulo `src/pdf2md/vault.py`). Copia los `.md` a `vault_dir`
> con nombre saneado, front matter enriquecido (`aliases` + tag `pdf-importado`,
> sin borrar tus tags), un **`Índice.md`** navegable (wikilinks) y un
> **`_indice.jsonl`** (puente al retriever). No pisa notas ya publicadas
> (`--overwrite` para forzar). Configúralo con `vault_dir` en `config.yaml`.

| Mejora | Impacto | Esfuerzo | Notas |
|---|---|---|---|
| ✅ **Índice global** | Alto | Bajo | Hecho: `Índice.md` (navegable) + `_indice.jsonl` (para el retriever). |
| ✅ **Nombres normalizados (slug)** | Medio | Bajo | Hecho: `slugify_filename` (seguro para Obsidian, mantiene acentos). |
| ✅ **Organización por formato** | Medio | Bajo | Hecho: `organizar.py` agrupa la bóveda en `Mapa - PDF/Word/Excel` (tag `origen/…`). |
| ✅ **Publicación automática** | Medio | Bajo | **Hecho:** el modo vigilancia (`watch.py`) publica, organiza y —con `auto_relate`— relaciona cada archivo nuevo; la GUI lo activa desde la pestaña "Vigilar carpeta" (campo bóveda + casilla "enviar a Obsidian y organizar"). |
| **Metadatos más ricos** | Medio | Medio | Word ya aporta `words`. Pendiente: hash del documento (id estable), fecha detectada en el texto, tipo (factura/carta/legal). |
| ✅ **Tags y wikilinks automáticos** | Medio | Medio | **Hecho (Fase 2.6):** relaciones semánticas por tema/entidad/evento. Ver abajo. |

### ✅ Fase 2.6 — Relaciones semánticas (hecho)

`relacionar.py` / `relacionar.bat` (módulo `src/pdf2md/semantics/`) analiza el
contenido de las notas y las enlaza cuando tratan del mismo **tema, proyecto,
entidad o evento**, aunque no usen las mismas palabras (puente por **jerarquía de
conceptos** en `data/conceptos.yaml`). Escribe tags `tema/…` `evento/…`
`entidad/…`, `keywords`, la propiedad `related` y una sección **🔗 Notas
relacionadas** con nivel de confianza; crea mapas `Tema - X` y `Mapa de Temas`.
Prioriza la **precisión** (umbral + top-K + corroboración). Sin dependencias
pesadas (embeddings opcionales tras `BaseEmbedder`). Índice incremental
(`_semantica.json`). Documentación completa en **`docs/RELACIONES.md`**.

---

## Fase 2.5 — Exportar de vuelta a PDF (bóveda → PDF)

> El "viaje de vuelta": tomar los `.md` (ya curados en Obsidian) y generar un
> **PDF limpio nuevo** — texto real, seleccionable y buscable. **No** es el
> escaneo original idéntico (PDF→MD es con pérdida: se pierde maquetación,
> firmas e imágenes); es un PDF tipográfico, normalmente mejor para leer.

| Opción | Impacto | Esfuerzo | Notas |
|---|---|---|---|
| **Export nativo de Obsidian** | Bajo | Nulo | `···` → *Export to PDF*. Manual, de uno en uno. Cero código. |
| ⭐ **Script `exportar_pdf.py` (Python)** | Alto | Medio | `markdown` + **WeasyPrint**: recorre la bóveda, quita el front matter y las marcas `<!-- página N -->`, y genera un PDF por nota. Encaja con el proyecto. |
| **Pandoc (lote con LaTeX)** | Medio | Medio | Mejor tipografía, pero exige instalar un motor LaTeX. |

---

## Fase 3 — Indexación (núcleo del RAG)

> Preparar los documentos para búsqueda semántica. Rellena las interfaces ya
> esbozadas en `src/pdf2md/rag/interfaces.py`.

| Mejora | Impacto | Esfuerzo | Notas |
|---|---|---|---|
| **Exportar chunks a disco** | Alto | Bajo | `HeadingChunker` ya existe; volcar los fragmentos a JSONL (con `heading_path` y página). |
| **Embeddings** | Alto | Medio | `sentence-transformers` multilingüe (local) u OpenAI. Implementar `BaseEmbedder`. |
| **Base de datos vectorial** | Alto | Medio | **Chroma** o **FAISS**. Implementar `BaseVectorStore`. |

---

## Fase 4 — RAG / consultas

> El objetivo final: preguntar en lenguaje natural sobre tus documentos.

| Mejora | Impacto | Esfuerzo | Notas |
|---|---|---|---|
| **Retriever + LLM** | Alto | Alto | Búsqueda semántica → contexto → respuesta, **citando la página** (gracias a las marcas `<!-- página N -->`). |
| **Interfaz de preguntas** | Alto | Medio | Pestaña de chat en la GUI, o CLI de consultas. |

---

## Mejoras transversales

| Mejora | Impacto | Esfuerzo | Notas |
|---|---|---|---|
| **Redacción de datos sensibles** | Medio | Medio | Ocultar RNC, cédulas, teléfonos antes de indexar (tus documentos son reales). |
| **Vista previa del Markdown** | Medio | Medio | Panel lado a lado en la interfaz. |
| **Deduplicación por hash** | Bajo | Bajo | No reconvertir un PDF ya procesado. |
| **Arranque automático (Windows)** | Bajo | Bajo | Vigilancia al iniciar sesión (Programador de tareas). |

---

## 🎯 Próximos 3 pasos recomendados

1. **Tablas sin bordes** (Fase 1.5) — arregla el fallo real de tus facturas.
2. **Preprocesado de imagen para OCR** (Fase 1.5) — sube la precisión en escaneos.
3. **Índice global + pruebas reales** (Fases 2 y 1.6) — base sólida y primer
   puente hacia el RAG.

> Limitaciones actuales conocidas (tablas sin bordes, firmas marcadas como
> títulos, títulos en escaneos) están documentadas en el **README, sección 14**.
