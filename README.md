# Documentos (PDF · Word · Excel) → Markdown

Conversor de documentos **PDF (digitales o escaneados), Word (`.docx`) y Excel (`.xlsx`)
→ Markdown estructurado y con metadatos**. Es la **Fase 1** de un sistema RAG mayor.
El objetivo aquí es **una sola cosa, bien hecha**: extraer el contenido con la máxima
fidelidad y estructura posibles, porque *si la extracción inicial es mala, el RAG
posterior también lo será*.

> El PDF —sobre todo el escaneado— es el caso más difícil, así que este README lo usa
> como hilo conductor. **Word y Excel recorren el mismo pipeline** y se documentan en
> [§6](#6-preservación-de-la-estructura). Los tres formatos comparten salida, metadatos
> y publicación a Obsidian.

> Esta versión **NO** incluye embeddings, bases de datos vectoriales ni chatbot.
> La arquitectura ya está preparada para añadirlos (ver [§15](#15-arquitectura-preparada-para-rag)).

> **Fases posteriores ya construidas** (cómo lanzarlas: [§13, opción D](#13-cómo-ejecutar);
> documentación detallada aparte):
> - **Fase 2 — Obsidian:** publicar (`publicar.py`) y organizar por formato
>   (`organizar.py`) tus notas en una bóveda.
> - **Fase 2.6 — Relaciones semánticas:** `relacionar.py` enlaza las notas por
>   tema, entidad y evento (aunque no compartan las mismas palabras). Ver
>   **[`docs/RELACIONES.md`](docs/RELACIONES.md)** y el [ROADMAP](ROADMAP.md).

---

## Índice

1. [Arquitectura del sistema](#1-arquitectura-del-sistema)
2. [Lenguaje y tecnologías](#2-lenguaje-y-tecnologías)
3. [Librerías de extracción de PDF](#3-librerías-de-extracción-de-pdf)
4. [Herramientas de OCR](#4-herramientas-de-ocr)
5. [Detección: digital vs. escaneado](#5-detección-digital-vs-escaneado)
6. [Preservación de la estructura](#6-preservación-de-la-estructura)
7. [Limpieza y corrección del OCR](#7-limpieza-y-corrección-del-ocr)
8. [Estructura de carpetas](#8-estructura-de-carpetas)
9. [Formato del Markdown](#9-formato-del-markdown)
10. [Manejo de errores](#10-manejo-de-errores)
11. [Procesamiento de múltiples documentos](#11-procesamiento-de-múltiples-documentos)
12. [Instalación](#12-instalación)
13. [Cómo ejecutar](#13-cómo-ejecutar)
14. [Limitaciones y vías de mejora](#14-limitaciones-y-vías-de-mejora)
15. [Arquitectura preparada para RAG](#15-arquitectura-preparada-para-rag)

---

## 1. Arquitectura del sistema

Pipeline modular; cada paso es una pieza reemplazable:

```text
                      ┌──────────────────────────────────────────────┐
   PDF  ─────────────▶│                  pipeline.py                  │
                      │  (orquesta y procesa por lotes)              │
                      └───────┬──────────────────────────────────────┘
                              │  por cada página:
                              ▼
                    ┌───────────────────┐
                    │   detector.py     │  ¿la página tiene texto?
                    └───┬───────────┬───┘
                 sí ▼               ▼ no
     ┌────────────────────┐   ┌──────────────┐
     │ text_extractor.py  │   │   ocr.py     │  (Tesseract)
     │  (PyMuPDF)         │   │  (Pillow +   │
     │  títulos/listas/   │   │   pytesseract)│
     │  tablas/párrafos   │   └──────┬───────┘
     └─────────┬──────────┘          │
               └────────┬────────────┘
                        ▼
                 ┌──────────────┐
                 │ cleaning.py  │  normaliza, de-hifena, quita cabeceras/pies
                 └──────┬───────┘
                        ▼
                 ┌──────────────────┐
                 │ markdown_writer  │  YAML front matter + cuerpo Markdown
                 └──────┬───────────┘
                        ▼
              documentos/markdown/*.md
```

**Modelo de datos común** (`models.py`): cada documento —sea PDF, Word o Excel— se
convierte en un `DocumentResult` → lista de `Page` → lista de `Block` (`HEADING`,
`PARAGRAPH`, `LIST`, `TABLE`). Un **despachador** (`pipeline.convert_file`) elige el
lector según la extensión, pero todos entregan la **misma** estructura; por eso todo
lo demás (limpieza, Markdown, publicación a Obsidian, chunking para RAG) opera igual
sobre los tres formatos, sin reescribir nada.

| Archivo | Responsabilidad |
|---|---|
| `main.py` | CLI: argumentos y arranque |
| `src/pdf2md/config.py` | Configuración (config.yaml + defaults) |
| `src/pdf2md/pipeline.py` | Orquestación, lotes y despachador `convert_file` (elige lector por extensión) |
| `src/pdf2md/detector.py` | Decide por página: digital u OCR |
| `src/pdf2md/text_extractor.py` | PDF digital → bloques (PyMuPDF) |
| `src/pdf2md/ocr.py` | PDF escaneado → bloques (Tesseract) |
| `src/pdf2md/docx_extractor.py` | Word (`.docx`) → bloques (python-docx) |
| `src/pdf2md/xlsx_extractor.py` | Excel (`.xlsx`) → bloques (openpyxl) |
| `src/pdf2md/cleaning.py` | Limpieza y normalización |
| `src/pdf2md/markdown_writer.py` | Bloques → Markdown + metadatos |
| `src/pdf2md/vault.py` | Publicar y organizar en Obsidian (Fase 2) |
| `src/pdf2md/semantics/` | Relaciones semánticas entre notas (Fase 2.6) |
| `src/pdf2md/errors.py` | Errores y logging |
| `src/pdf2md/rag/` | Interfaces preparadas para las Fases 3-4 |

---

## 2. Lenguaje y tecnologías

**Python 3.10+** (probado en 3.14). Es el ecosistema con mejores librerías de PDF,
OCR y, más adelante, RAG (LangChain, sentence-transformers, FAISS/Chroma…).

| Necesidad | Elección | Por qué |
|---|---|---|
| Extracción de PDF | **PyMuPDF** | Rápida, da tamaños de fuente, posiciones y detecta tablas |
| Render para OCR | **PyMuPDF + Pillow** | Convierte cada página a imagen a DPI configurable |
| OCR | **Tesseract** (vía **pytesseract**) | Libre, local, excelente soporte de español |
| Lectura de Word | **python-docx** | Recorre párrafos y tablas en orden, con estilos |
| Lectura de Excel | **openpyxl** | Lee hojas y celdas (modo `read_only`, `data_only`) |
| Config / CLI | **PyYAML + argparse** | Estándar y sin fricción |
| Progreso | **tqdm** | Barra de progreso en lotes |
| Interfaz gráfica | **Tkinter** | Incluido con Python, sin dependencias extra |

---

## 3. Librerías de extracción de PDF

- **PyMuPDF (`fitz`)** — motor principal. `get_text("dict")` da el texto con
  **tamaño de fuente, negrita y posición** (base para inferir títulos), y
  `find_tables()` detecta tablas devolviendo su recuadro y sus celdas.
- **Alternativas** (comentadas en `requirements.txt`), útiles si algún PDF se
  resiste: **pdfplumber** (tablas complejas), **camelot** (tablas con líneas).

---

## 4. Herramientas de OCR

- **Tesseract OCR** vía **pytesseract**. Se usa `image_to_data`, que además del
  texto devuelve **confianza por palabra** y su **posición/altura** → sirve para
  reconstruir párrafos y títulos y para **marcar** palabras dudosas.
- Idioma español: paquete `spa` (para documentos bilingües, `spa+eng`).
- **Alternativas** (documentadas, no instaladas): **OCRmyPDF**, **EasyOCR**,
  **PaddleOCR**, **docTR**; y servicios/LLM de visión para máxima calidad.

> ⚠️ Tesseract es un programa del sistema: **no** se instala con `pip`. Ver [§12](#12-instalación).
> Si no está instalado, las páginas digitales se convierten igual y las escaneadas
> se marcan como pendientes en la carpeta `errores/` (el lote no se detiene).

---

## 5. Detección: digital vs. escaneado

`detector.py`, **por página** (un PDF puede ser mixto):

1. Se extrae el texto con PyMuPDF.
2. Si supera un umbral de caracteres alfanuméricos (`min_chars_text`, def. 100)
   → **digital** (extracción directa).
3. Si está casi vacía → **escaneada** → OCR.

El umbral es configurable en `config.yaml`.

---

## 6. Preservación de la estructura

| Elemento | En PDF digital | En PDF escaneado (OCR) |
|---|---|---|
| **Títulos** | Tamaño de fuente > cuerpo (+ negrita); niveles H1–H4 por ranking de tamaños | Altura del texto notablemente mayor que la media |
| **Párrafos** | Agrupación por bloques; unión de líneas y de-hifenado | Agrupación por párrafo de Tesseract |
| **Listas** | Marcador inicial (`-`, `•`, `1.`, `a)`…) | Igual, sobre el texto OCR |
| **Tablas** | `page.find_tables()` de PyMuPDF → Markdown | (no en Fase 1; ver [§14](#14-limitaciones-y-vías-de-mejora)) |
| **Orden de lectura** | Bloques ordenados por posición vertical | Orden natural de Tesseract |
| **Nº de página** | Comentario `<!-- página N -->` (opcional) | Igual |

El **modelo de tamaños de fuente se calcula para todo el documento**, de modo
que los niveles de título salen consistentes en todo el `.md`.

### Word y Excel

Además de PDF, el conversor lee **Word (`.docx`)** y **Excel (`.xlsx`)** con el mismo
resultado (`DocumentResult` → Markdown). El despachador `convert_file` importa el
lector correcto sólo cuando hace falta:

| Formato | Lector | Cómo se preserva la estructura |
|---|---|---|
| **Word** (`.docx`) | `python-docx` | Recorre el cuerpo del documento **en su orden real** (párrafos y tablas intercalados); mapea los estilos *Título/Heading* a `#…`, los de lista a listas y las tablas a Markdown. Añade el metadato `words` (nº de palabras). |
| **Excel** (`.xlsx`) | `openpyxl` (`read_only`, `data_only`) | Cada hoja → un encabezado `##` + una tabla Markdown; recorta filas/columnas vacías, con un tope de seguridad de **5000 filas por hoja**. |

> Los formatos antiguos **`.doc` y `.xls`** **no** están soportados: ábrelos en Office
> y guárdalos como `.docx`/`.xlsx` (el programa avisa con un mensaje claro). Los
> temporales `~$…` de Office se ignoran en los lotes.

---

## 7. Limpieza y corrección del OCR

`cleaning.py`, con una regla de oro: **limpiar sin inventar**.

- Normaliza espacios y elimina caracteres de control.
- Corrige ligaduras tipográficas (`ﬁ`→`fi`).
- **De-hifenado** de fin de línea (`compañe-\nros` → `compañeros`).
- Elimina **cabeceras/pies repetidos** en la mayoría de páginas.
- Las palabras con **baja confianza de OCR** **no** se corrigen a la fuerza: se
  registran como avisos en `documentos/errores/<archivo>_avisos.txt` y la
  confianza media va en los metadatos, para que las revises tú.

*(Opcional a futuro: corrector ortográfico español con `pyspellchecker` o
`language_tool_python`; dejado fuera por defecto para no alterar el contenido.)*

---

## 8. Estructura de carpetas

```text
PDF a MD/
├── main.py                 # punto de entrada (CLI)
├── gui.py                  # interfaz gráfica (Tkinter)   ·  interfaz.bat  (lanzador)
├── watch.py                # modo automático (vigila una carpeta)  ·  vigilar.bat
├── publicar.py             # Fase 2: publicar los .md en una bóveda de Obsidian  ·  publicar.bat
├── organizar.py            # Fase 2: agrupar la bóveda por formato (PDF/Word/Excel)
├── relacionar.py           # Fase 2.6: relaciones semánticas entre notas  ·  relacionar.bat
├── config.yaml             # configuración (conversión + Obsidian + relaciones)
├── requirements.txt
├── README.md   ROADMAP.md   docs/RELACIONES.md
├── generar_doc.py          # genera Documentacion.pdf (manual completo)
├── tessdata/               # idiomas de Tesseract (spa.traineddata)
├── documentos/
│   ├── originales/         # ← documentos (PDF/Word/Excel) para el modo CLI/interfaz
│   ├── entrada/            # ← documentos nuevos para el modo automático
│   ├── markdown/           # → salida .md
│   ├── procesados/         # → originales ya convertidos (modo automático)
│   └── errores/            # → logs de fallos y avisos
├── src/pdf2md/             # el paquete
│   ├── detector.py  text_extractor.py  ocr.py        # PDF (digital / escaneado)
│   ├── docx_extractor.py  xlsx_extractor.py          # Word / Excel
│   ├── cleaning.py  markdown_writer.py  pipeline.py
│   ├── models.py  config.py  errors.py  textutils.py
│   ├── vault.py            # publicar/organizar en Obsidian (Fases 2)
│   ├── semantics/          # relaciones semánticas (Fase 2.6); data/conceptos.yaml
│   └── rag/                # interfaces para las Fases 3-4 (no implementadas)
└── tests/                  # test_smoke.py  ·  test_semantics.py
```

> La **bóveda de Obsidian** vive fuera del proyecto (`vault_dir` en `config.yaml`); es
> una carpeta cualquiera de archivos `.md`. Ver [§13, opción D](#13-cómo-ejecutar).

---

## 9. Formato del Markdown

Cada `.md` empieza con **YAML Front Matter** (clave para el RAG) y sigue con el
contenido estructurado:

```markdown
---
title: "Nombre del documento"
source: "documento_original.pdf"
file_type: "pdf"
pages: 25
ocr: true
language: "es"
date_processed: "2026-08-09"
ocr_pages: 25
ocr_confidence: 92.4
tags: []
---

<!-- página 1 -->
# Título del documento

## Introducción
Texto del documento…

| Nombre | Edad | Ciudad |
| --- | --- | --- |
| Juan | 25 | Santo Domingo |
```

Los comentarios `<!-- página N -->` son invisibles al leer el Markdown pero
permiten al futuro RAG **citar la página de origen** de cada respuesta.

El campo `file_type` refleja el origen (`pdf`, `docx` o `xlsx`). Los metadatos de OCR
(`ocr`, `ocr_pages`, `ocr_confidence`) sólo aparecen cuando hubo páginas escaneadas;
Word añade `words` (nº de palabras). Al **publicar en Obsidian** (Fase 2) el front
matter se enriquece con `aliases`, tags y —si activas la Fase 2.6— `keywords`,
`related` y una sección *🔗 Notas relacionadas* (ver [`docs/RELACIONES.md`](docs/RELACIONES.md)).

---

## 10. Manejo de errores

- Cada documento se procesa de forma **aislada**: si uno falla, el lote continúa.
- Los fallos se guardan en `documentos/errores/`:
  - `documentos_con_problemas.txt` — índice (fecha · archivo · error).
  - `<archivo>_<fecha>.log` — traza completa.
  - `<archivo>_avisos.txt` — avisos no fatales (p. ej., baja confianza OCR).
- Casos contemplados: PDF corrupto/ilegible, **PDF cifrado**, OCR no disponible,
  páginas escaneadas sin texto reconocible, y formatos antiguos `.doc`/`.xls`
  (con un mensaje que pide guardarlos como `.docx`/`.xlsx`).

---

## 11. Procesamiento de múltiples documentos

- `python main.py` convierte **todos** los documentos (PDF, Word y Excel) de
  `documentos/originales/`.
- `--recursive` incluye subcarpetas.
- Por defecto **no** re-procesa un `.md` que ya existe (usa `--overwrite` para forzar).
- Barra de progreso con `tqdm` y resumen final (OK / omitidos / con error).
- Se mantiene la **relación 1:1** `documento.pdf|docx|xlsx` → `documento.md`.

---

## 12. Instalación

**a) Dependencias de Python**

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows (PowerShell:  .venv\Scripts\Activate.ps1)
pip install -r requirements.txt
```

**b) Tesseract OCR** (sólo si vas a procesar escaneados; es un programa aparte):

```bash
winget install -e --id UB-Mannheim.TesseractOCR
```

**c) Idioma español para Tesseract.** La instalación silenciosa trae *solo inglés*.
El español (`spa`) ya viene descargado en la carpeta `tessdata/` de este proyecto,
y `config.yaml` la apunta con `tessdata_dir: "tessdata"`. Si necesitaras volver a
descargarlo:

```bash
# PowerShell, desde la carpeta del proyecto
Invoke-WebRequest "https://github.com/tesseract-ocr/tessdata/raw/main/spa.traineddata" -OutFile "tessdata/spa.traineddata"
```

> Para máxima calidad puedes usar la variante `tessdata_best` en vez de `tessdata`
> (misma URL cambiando el nombre del repo); es más lenta pero más precisa.

**Rutas en `config.yaml`** (ya configuradas para una instalación estándar en Windows):

```yaml
tesseract_cmd: "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"  # null si está en el PATH
tessdata_dir: "tessdata"   # o null para usar la carpeta de idiomas de Tesseract
```

Si algún día instalas el español en la carpeta oficial de Tesseract (necesita
permisos de administrador), puedes poner `tessdata_dir: null`.

---

## 13. Cómo ejecutar

### Opción A — Interfaz gráfica (la más fácil)

Doble clic en **`interfaz.bat`**, o bien:

```bash
python gui.py
```

La ventana tiene **dos pestañas**:

- **Convertir archivos:** agrega documentos (PDF · Word · Excel) o una carpeta,
  elige la carpeta de salida, pulsa **Convertir** y ve el progreso y el resultado
  por archivo. Se puede **cancelar** y hay botones para abrir la carpeta de salida
  y la de errores.
- **Vigilar carpeta:** elige con botones la carpeta de **ENTRADA** y la de
  **SALIDA** (y la de procesados), pulsa **Iniciar vigilancia** y cada documento que
  llegue a la entrada se convierte solo. **Detener** cuando quieras. Aquí también
  puedes indicar tu **bóveda de Obsidian** y marcar *«enviar a Obsidian y organizar
  por formato»*: entonces cada archivo, al convertirse, se **publica, organiza y
  —si `auto_relate` está activo— relaciona** en la bóveda, sin tocar nada
  (ciclo completo; ver opción D).

Debajo hay opciones comunes (tablas, cabeceras/pies, idioma OCR, DPI…). Todo el
trabajo corre en segundo plano (la ventana no se congela) y no necesita
dependencias extra (Tkinter viene con Python).

### Opción B — Línea de comandos

```bash
# 1) Coloca tus documentos (PDF/Word/Excel) en  documentos/originales/  y luego:
python main.py

# Un archivo o carpeta concretos:
python main.py -i "C:\\ruta\\a\\mi.pdf"      # o mi.docx / mi.xlsx
python main.py -i entrada -o salida --recursive --overwrite

# Ajustes de OCR:
python main.py --ocr-lang spa+eng --dpi 400
```

### Opción C — Modo automático (carpeta vigilada)

Doble clic en **`vigilar.bat`**, o bien:

```bash
python watch.py
```

Deja la ventana abierta: cada documento (PDF, Word o Excel) que copies o guardes en
**`documentos/entrada/`** se convierte solo, el `.md` aparece en
**`documentos/markdown/`** y el original se mueve a **`documentos/procesados/`**
(si algo falla, va a `documentos/errores/`). Detecta cuándo el archivo terminó de
copiarse (comprueba que su tamaño se estabiliza), así que nunca convierte uno a medio
copiar. Pulsa **Ctrl+C** o cierra la ventana para detenerlo. Carpetas e intervalo son
configurables:

```bash
python watch.py -w documentos/entrada -o documentos/markdown --interval 5
```

> **Ciclo completo hacia Obsidian.** Si hay una bóveda configurada (`vault_dir` en
> `config.yaml`, o la salida apunta a ella), la vigilancia además **publica** cada
> `.md` en la bóveda y la **organiza por formato**; y con `auto_relate: true`, teje
> también las **relaciones semánticas**. Si Obsidian falla, la conversión no se pierde
> (el `.md` queda en la salida). Ver **opción D** y [`docs/RELACIONES.md`](docs/RELACIONES.md).

> **Que arranque solo con Windows:** crea una tarea en el *Programador de tareas*
> (al iniciar sesión → `vigilar.bat`), o coloca un acceso directo a `vigilar.bat`
> en la carpeta *Inicio* (`Win+R` → `shell:startup`).

### Opción D — Publicar y conectar en Obsidian (Fases 2 y 2.6)

Estos pasos toman los `.md` ya convertidos y construyen una base de conocimiento
navegable. Puedes lanzarlos a mano (o dejar que la vigilancia los haga por ti, arriba):

```bash
python publicar.py     # copia los .md a la bóveda (vault_dir) + Índice + front matter
python organizar.py    # agrupa la bóveda por formato: Mapa - PDF/Word/Excel
python relacionar.py   # enlaza las notas por tema/entidad/evento (🔗 Notas relacionadas)
```

También por doble clic: `publicar.bat` y `relacionar.bat`. Detalle completo de las
relaciones semánticas en **[`docs/RELACIONES.md`](docs/RELACIONES.md)**; el plan de
fases, en **[ROADMAP.md](ROADMAP.md)**.

Comprobar la lógica sin documentos ni Tesseract:

```bash
python tests/test_smoke.py       # pipeline de conversión
python tests/test_semantics.py   # relaciones semánticas (Fase 2.6)
```

---

## 14. Limitaciones y vías de mejora

- **Detección de títulos/tablas** es heurística: muy buena en documentos
  regulares, mejorable en diseños complejos (multicolumna, formularios).
- **Tablas SIN líneas de rejilla** (facturas con columnas alineadas por espacios):
  `page.find_tables()` necesita líneas visibles, así que estas tablas quedan como
  texto plano (el contenido y los importes se conservan, pero no la rejilla).
  Vía de mejora: respaldo con **pdfplumber** por estrategia de alineación de texto.
- **Bloques de firma / texto en negrita centrado** pueden marcarse como títulos
  por error (el detector de encabezados usa tamaño/negrita).
- **Tablas en escaneados**: no en la Fase 1 (reconstruir la rejilla desde una
  imagen es frágil). Vía de mejora: `page.find_tables()` sobre un PDF con capa
  OCR generada por **OCRmyPDF**.
- **Salto de calidad "llave en mano"**: para documentos difíciles, herramientas
  como **Docling** o **Marker** producen Markdown de muy alta calidad y encajan
  como un extractor alternativo detrás de la misma interfaz de `pipeline.py`.

---

## 15. Arquitectura preparada para RAG

Sin implementar todavía embeddings ni vector DB, la Fase 1 ya deja el terreno listo:

1. **Metadatos YAML** en cada `.md` → filtros y citas.
2. **Marcas de página** `<!-- página N -->` → trazabilidad de la respuesta.
3. **Estructura por títulos** → chunking semántico natural (no cortar a ciegas).
4. **Interfaces ya definidas** en `src/pdf2md/rag/interfaces.py`:
   - `HeadingChunker` — **ya implementado**: parte el `.md` por secciones y
     conserva `heading_path` + `page` en cada `Chunk`.
   - `BaseEmbedder`, `BaseVectorStore` — contratos vacíos para la Fase 3.

Cuando lleguemos al RAG, el flujo será:

```text
Markdown → HeadingChunker → Embedder → VectorStore → Retriever → LLM → Respuesta
```

y sólo habrá que **rellenar** `BaseEmbedder`/`BaseVectorStore` (p. ej.
sentence-transformers + FAISS/Chroma) sin tocar la conversión.
