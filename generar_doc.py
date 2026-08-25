# -*- coding: utf-8 -*-
"""Genera la documentacion completa del proyecto en PDF con reportlab."""
import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                Preformatted, PageBreak, KeepTogether, HRFlowable)

OUT = r"C:\Users\giovy\Downloads\PDF a MD\Documentacion.pdf"
FECHA = datetime.date.today().strftime("%d/%m/%Y")

# ------- colores -------
GREEN_DARK = colors.HexColor("#0f3d31")
GREEN = colors.HexColor("#0f6e56")
GREEN_LIGHT = colors.HexColor("#9fe1cb")
GREEN_BG = colors.HexColor("#e1f5ee")
GRAY = colors.HexColor("#d0d7de")
CODE_BG = colors.HexColor("#f6f8fa")
AMBER_BG = colors.HexColor("#faeeda")
AMBER = colors.HexColor("#ef9f27")
TEXT = colors.HexColor("#1f2328")
MUTED = colors.HexColor("#57606a")
WHITE = colors.white

# ------- estilos -------
body = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, leading=15,
                      textColor=TEXT, spaceAfter=6)
h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, leading=20,
                    textColor=GREEN_DARK, spaceBefore=20, spaceAfter=4, keepWithNext=True)
h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, leading=16,
                    textColor=GREEN, spaceBefore=12, spaceAfter=3, keepWithNext=True)
h3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=11, leading=14,
                    textColor=TEXT, spaceBefore=8, spaceAfter=2, keepWithNext=True)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=16, bulletIndent=4, spaceAfter=3)
cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=12, textColor=TEXT)
cellhead = ParagraphStyle("cellhead", fontName="Helvetica-Bold", fontSize=9, leading=12,
                          textColor=WHITE)
codest = ParagraphStyle("code", fontName="Courier", fontSize=8.5, leading=12, textColor=TEXT)

CONTENT_W = A4[0] - 36 * mm   # ancho util (margenes de 18mm)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def k(s):   # inline code
    return f'<font face="Courier" size="9" color="#0a3a2c">{esc(s)}</font>'


def H1(text):
    return [Paragraph(esc(text), h1),
            HRFlowable(width="100%", thickness=1.5, color=GREEN_LIGHT,
                       spaceBefore=1, spaceAfter=8)]


def H2(text):
    return [Paragraph(esc(text), h2)]


def H3(text):
    return [Paragraph(esc(text), h3)]


def P(html):
    return [Paragraph(html, body)]


def UL(items):
    return [Paragraph(it, bullet, bulletText="\u2022") for it in items]


def CODE(text):
    safe = esc(text).replace(" ", "&nbsp;").replace("\n", "<br/>")
    inner = Paragraph(safe, codest)
    t = Table([[inner]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, GRAY),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [Spacer(1, 2), KeepTogether(t), Spacer(1, 6)]


def CALLOUT(html):
    p = Paragraph(html, ParagraphStyle("co", parent=body, spaceAfter=0))
    t = Table([[p]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AMBER_BG),
        ("LINEBEFORE", (0, 0), (0, -1), 3, AMBER),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [Spacer(1, 2), KeepTogether(t), Spacer(1, 8)]


def TABLE(rows, widths):
    data = []
    for i, row in enumerate(rows):
        st = cellhead if i == 0 else cell
        data.append([Paragraph(c, st) for c in row])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("GRID", (0, 0), (-1, -1), 0.5, GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return [Spacer(1, 2), t, Spacer(1, 8)]


# ===================== contenido =====================
S = []

# ---- Portada ----
S += [HRFlowable(width="100%", thickness=8, color=GREEN, spaceAfter=0)]
S += [Spacer(1, 150)]
S += [Paragraph("PDF, Word y Excel a Markdown",
                ParagraphStyle("ct", fontName="Helvetica-Bold", fontSize=30, leading=34,
                               textColor=GREEN_DARK, spaceAfter=6))]
S += [Paragraph("Conversor a Markdown estructurado  &nbsp;&middot;&nbsp;  Fase 1 del sistema RAG",
                ParagraphStyle("cs", fontName="Helvetica", fontSize=14, leading=18,
                               textColor=GREEN, spaceAfter=40))]
S += [Paragraph(f"Documentaci&oacute;n completa del programa<br/>Versi&oacute;n 0.3<br/>"
                f"Fecha: {FECHA}<br/>Autor: Giovy Polanco",
                ParagraphStyle("cm", fontName="Helvetica", fontSize=11, leading=19,
                               textColor=MUTED))]
S += [Spacer(1, 50)]
_cov = Paragraph("Convierte documentos (PDF digitales o escaneados, Word y Excel) a "
                 "Markdown estructurado y con metadatos, los publica en una b&oacute;veda de "
                 "Obsidian, los organiza por formato y los conecta por significado. Es la base "
                 "de un sistema RAG por etapas: la calidad de esta conversi&oacute;n determina la "
                 "calidad de todo lo que viene despu&eacute;s.",
                 ParagraphStyle("cn", parent=body, spaceAfter=0))
_covt = Table([[_cov]], colWidths=[CONTENT_W])
_covt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GREEN_BG),
                           ("LINEBEFORE", (0, 0), (0, -1), 3, GREEN_LIGHT),
                           ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                           ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
S += [_covt, PageBreak()]

# ---- Indice ----
S += H1("Contenido")
_toc = ["1.  Qu&eacute; es el programa", "2.  Qu&eacute; convierte (PDF, Word, Excel)",
        "3.  Requisitos", "4.  Instalaci&oacute;n", "5.  C&oacute;mo se usa (interfaz, terminal, vigilancia)",
        "6.  Publicar, organizar y conectar en Obsidian", "7.  C&oacute;mo se convierte cada formato",
        "8.  El Markdown de salida", "9.  Configuraci&oacute;n (config.yaml)",
        "10.  C&oacute;mo funciona por dentro", "11.  Errores y soluci&oacute;n de problemas",
        "12.  Limitaciones conocidas", "13.  Roadmap (pr&oacute;ximas fases)"]
S += [Paragraph(t, ParagraphStyle("toc", parent=body, spaceAfter=5, fontSize=11)) for t in _toc]
S += [PageBreak()]

# ---- 1 ----
S += H1("1. Qu\u00e9 es el programa")
S += P("Es un conversor que toma tus documentos y los transforma en <b>Markdown</b> "
       f"({k('.md')}): texto limpio, estructurado (t&iacute;tulos, listas, tablas) y con "
       "metadatos. Adem&aacute;s puede <b>publicarlos autom&aacute;ticamente en una b&oacute;veda de "
       "Obsidian</b> para navegarlos como una base de conocimiento.")
S += P("Es la <b>Fase 1</b> de un sistema mayor (un RAG: un chatbot que responde "
       "preguntas sobre tus propios documentos). La regla que gu&iacute;a el proyecto: "
       "<b>primero la calidad de la conversi&oacute;n</b>, porque si la extracci&oacute;n inicial "
       "es mala, todo lo que se construya encima tambi&eacute;n lo ser&aacute;.")
S += H2("Lo que ya hace")
S += UL(["Convierte <b>PDF</b> digitales y <b>escaneados</b> (con OCR en espa&ntilde;ol).",
         "Convierte <b>Word (.docx)</b> y <b>Excel (.xlsx)</b>.",
         "Detecta si un PDF es digital o escaneado, p&aacute;gina por p&aacute;gina.",
         "Reconoce t&iacute;tulos, listas, p&aacute;rrafos y tablas.",
         "Escribe metadatos (YAML) y marcas de p&aacute;gina para citar el origen.",
         "Tres formas de uso: interfaz gr&aacute;fica, terminal y modo autom&aacute;tico.",
         "Publica el resultado en Obsidian con un &iacute;ndice navegable.",
         "<b>Organiza</b> la b&oacute;veda por formato y <b>conecta las notas por significado</b> "
         "(tema, entidad, evento), aunque no usen las mismas palabras.",
         "Puede hacer <b>todo el ciclo autom&aacute;ticamente</b> al vigilar una carpeta."])

# ---- 2 ----
S += H1("2. Qu\u00e9 convierte (PDF, Word, Excel)")
S += P("El programa acepta tres formatos de entrada. Todos terminan en el mismo tipo de "
       "Markdown, as&iacute; que el resto del sistema funciona igual para los tres.")
S += TABLE([["Formato", "Ext.", "C&oacute;mo se lee", "Qu&eacute; se conserva"],
            ["PDF digital", ".pdf", "PyMuPDF", "T&iacute;tulos, p&aacute;rrafos, listas, tablas con l&iacute;neas"],
            ["PDF escaneado", ".pdf", "OCR (Tesseract)", "Texto reconocido; t&iacute;tulos por tama&ntilde;o"],
            ["Word", ".docx", "python-docx", "T&iacute;tulos por estilo, listas, tablas"],
            ["Excel", ".xlsx", "openpyxl", "Cada hoja como una tabla"]],
           [70, 40, 95, CONTENT_W - 205])
S += CALLOUT(f"Los formatos antiguos {k('.doc')} y {k('.xls')} no est&aacute;n soportados. "
             f"&Aacute;brelos en Office y gu&aacute;rdalos como {k('.docx')} o {k('.xlsx')}. El programa "
             "te avisa con un mensaje claro si intentas uno.")

# ---- 3 ----
S += H1("3. Requisitos")
S += H2("Del sistema (no se instalan con pip)")
S += UL(["<b>Python 3.10 o superior</b> (probado en 3.14.5).",
         f"<b>Tesseract OCR 5.x</b> &mdash; solo para PDF escaneados. Instalar con {k('winget install UB-Mannheim.TesseractOCR')}.",
         "<b>Tkinter</b> &mdash; la interfaz gr&aacute;fica; viene incluido con Python."])
S += H2("Paquetes de Python")
S += TABLE([["Paquete", "Versi&oacute;n", "Para qu&eacute;"],
            ["PyMuPDF", "1.28.2", "Leer PDF"],
            ["pytesseract", "0.3.13", "OCR de PDF escaneados"],
            ["Pillow", "12.2.0", "Im&aacute;genes para el OCR"],
            ["python-docx", "1.2.0", "Leer Word (.docx)"],
            ["openpyxl", "3.1.5", "Leer Excel (.xlsx)"],
            ["PyYAML", "6.0.3", "Leer config.yaml"],
            ["tqdm", "4.68.4", "Barra de progreso"]],
           [120, 70, CONTENT_W - 190])
S += CALLOUT("<b>Regla de oro:</b> instala los paquetes en el <b>mismo</b> Python con el que "
             "ejecutas el programa. Si usas los .bat (doble clic), ese es tu Python global. "
             "Un descuido aqu&iacute; es la causa m&aacute;s com&uacute;n del error 'Falta la librer&iacute;a python-docx'.")

# ---- 4 ----
S += H1("4. Instalaci\u00f3n")
S += P("<b>1) Paquetes de Python</b> (desde la carpeta del proyecto):")
S += CODE("pip install -r requirements.txt")
S += P("<b>2) Tesseract OCR</b> (solo si vas a convertir PDF escaneados):")
S += CODE("winget install -e --id UB-Mannheim.TesseractOCR")
S += P(f"<b>3) Idioma espa&ntilde;ol para Tesseract.</b> El archivo {k('spa.traineddata')} ya viene "
       f"en la carpeta {k('tessdata/')} del proyecto, y {k('config.yaml')} la apunta. No hay "
       "que hacer nada m&aacute;s.")

# ---- 5 ----
S += H1("5. C\u00f3mo se usa")
S += H2("A. Interfaz gr\u00e1fica (lo m\u00e1s f\u00e1cil)")
S += P(f"Doble clic en {k('interfaz.bat')} (o {k('python gui.py')}). Tiene dos pesta&ntilde;as:")
S += UL(["<b>Convertir archivos:</b> con 'Agregar archivos' eliges PDF, Word o Excel (o una "
         "carpeta), fijas la carpeta de salida y pulsas Convertir. Ves el progreso y puedes cancelar.",
         "<b>Vigilar carpeta:</b> eliges una carpeta de ENTRADA y otra de SALIDA; cada archivo "
         "que llegue se convierte solo. Si indicas tu b&oacute;veda y marcas 'enviar a Obsidian y "
         "organizar', adem&aacute;s se publica, organiza y (si est&aacute; activo) relaciona autom&aacute;ticamente."])
S += H2("B. Terminal (l\u00ednea de comandos)")
S += CODE('python main.py                         # convierte documentos/originales/\n'
          'python main.py -i "C:\\ruta\\a\\mi.docx"  # un archivo concreto\n'
          'python main.py -i entrada -o salida --recursive --overwrite\n'
          'python main.py --ocr-lang spa+eng --dpi 400   # ajustes de OCR')
S += H2("C. Modo autom\u00e1tico (carpeta vigilada)")
S += P(f"Doble clic en {k('vigilar.bat')} (o {k('python watch.py')}). Deja la ventana abierta: "
       "cada PDF, Word o Excel que copies a la carpeta de entrada se convierte solo, el .md "
       "aparece en la salida y el original pasa a 'procesados' (si algo falla, va a 'errores'). "
       "Detecta cu&aacute;ndo el archivo termin&oacute; de copiarse, as&iacute; que nunca convierte uno a medias.")
S += CODE("python watch.py -w documentos/entrada -o documentos/markdown --interval 5")
S += P(f"Si hay una b&oacute;veda configurada ({k('vault_dir')}), la vigilancia adem&aacute;s <b>publica, "
       f"organiza y conecta</b> cada archivo en Obsidian &mdash; el ciclo completo, sin tocar nada "
       f"(la parte de conectar requiere {k('auto_relate: true')}). Si Obsidian fallara, la "
       f"conversi&oacute;n no se pierde: el .md queda en la carpeta de salida.")

# ---- 6 ----
S += H1("6. Publicar, organizar y conectar en Obsidian")
S += P("Una b&oacute;veda de Obsidian es, simplemente, una <b>carpeta con archivos .md</b>. Tres "
       "pasos la convierten en una base de conocimiento navegable: <b>publicar</b> los .md, "
       "<b>organizarlos</b> por formato y <b>conectarlos</b> por significado. Puedes lanzarlos a "
       "mano o dejar que el modo autom&aacute;tico (secci&oacute;n 5C) los haga por ti.")

S += H2("Publicar  (publicar.py)")
S += P(f"El script {k('publicar.py')} (o {k('publicar.bat')}) toma los .md convertidos y los copia "
       "a tu b&oacute;veda:")
S += UL([f"Copia cada .md con un nombre seguro para Obsidian.",
         f"Enriquece el encabezado: a&ntilde;ade un {k('alias')} (el t&iacute;tulo) y la etiqueta "
         f"{k('pdf-importado')}, <b>sin borrar</b> las etiquetas que ya tuviera.",
         f"Genera un {k('Indice.md')} navegable, con enlaces a todos los documentos.",
         f"Genera un {k('_indice.jsonl')} (puente para el futuro buscador del RAG)."])
S += P(f"Por defecto <b>no</b> pisa notas ya publicadas (para no perder lo que edites en "
       f"Obsidian); usa {k('--overwrite')} para forzar. Configura la ruta de tu b&oacute;veda con "
       f"{k('vault_dir')} en {k('config.yaml')}.")
S += CODE('python publicar.py                       # usa las rutas de config.yaml\n'
          'python publicar.py -d "C:\\ruta\\a\\tu\\Boveda"')

S += H2("Organizar por formato  (organizar.py)")
S += P(f"{k('organizar.py')} agrupa cada nota seg&uacute;n de d&oacute;nde vino &mdash; <b>PDF, Word o "
       "Excel</b> &mdash;, le pone el tag correspondiente (" + k("origen/pdf") + ", "
       + k("origen/word") + "...), crea un <b>mapa por formato</b> ("
       + k("Mapa - PDF") + " / " + k("Word") + " / " + k("Excel") + ") que enlaza sus notas y "
       "regenera el &iacute;ndice. As&iacute;, en el grafo de Obsidian las notas dejan de estar sueltas y "
       "forman un racimo por formato. Es idempotente: al a&ntilde;adir notas, vuelve a ejecutarlo.")

S += H2("Conectar por significado  (relacionar.py — Fase 2.6)")
S += P(f"{k('relacionar.py')} (o {k('relacionar.bat')}) lee el contenido de cada nota y la enlaza "
       "con las que tratan del <b>mismo tema, proyecto, entidad o evento</b>, aunque no usen las "
       "mismas palabras (las conecta por una <b>jerarqu&iacute;a de conceptos</b>). Escribe tags "
       "(" + k("tema/...") + ", " + k("entidad/...") + ", " + k("evento/...") + "), "
       "palabras clave, la propiedad " + k("related") + " y una secci&oacute;n <b>'Notas "
       "relacionadas'</b> con su nivel de confianza; y crea mapas por tema. Prioriza la "
       "<b>precisi&oacute;n</b>: pocas relaciones, pero buenas. <b>No es destructivo</b>: s&oacute;lo "
       "reescribe el encabezado y esa secci&oacute;n marcada.")
S += CODE('python relacionar.py                     # usa las rutas de config.yaml\n'
          'python relacionar.py --threshold 0.25 --top-k 5')
S += CALLOUT("El conocimiento del dominio vive en "
             + k("src/pdf2md/semantics/data/conceptos.yaml") + " (datos, no c&oacute;digo): a&ntilde;ade "
             "ah&iacute; tus conceptos y sin&oacute;nimos para mejorar las relaciones. La gu&iacute;a completa "
             "est&aacute; en <b>docs/RELACIONES.md</b>.")

# ---- 7 ----
S += H1("7. C\u00f3mo se convierte cada formato")
S += H2("PDF")
S += P("Para cada p&aacute;gina se decide si es <b>digital</b> (tiene texto) o <b>escaneada</b> "
       "(es una imagen). La digital se extrae con PyMuPDF; la escaneada pasa por OCR "
       "(Tesseract). Los t&iacute;tulos se infieren por el tama&ntilde;o de fuente (digital) o por la "
       "altura del texto (escaneado). Las tablas con l&iacute;neas visibles se detectan.")
S += H2("Word (.docx)")
S += P("Se recorre el documento en orden real (p&aacute;rrafos y tablas intercalados). Los estilos "
       "'T&iacute;tulo 1/2/3' se convierten en encabezados; los estilos de lista, en listas; las "
       "tablas, en tablas Markdown; y el resto, en p&aacute;rrafos. Se guarda el conteo de palabras.")
S += H2("Excel (.xlsx)")
S += P("Cada hoja del libro se convierte en una tabla Markdown, precedida de un encabezado con "
       "el nombre de la hoja cuando hay m&aacute;s de una. Se recortan filas y columnas vac&iacute;as, con "
       "un l&iacute;mite de seguridad de 5000 filas por hoja.")

# ---- 8 ----
S += H1("8. El Markdown de salida")
S += P("Cada .md empieza con un bloque de metadatos (YAML) y sigue con el contenido "
       "estructurado. Ejemplo:")
S += CODE('---\n'
          'title: "Nombre del documento"\n'
          'source: "documento_original.pdf"\n'
          'file_type: "pdf"\n'
          'pages: 25\n'
          'ocr: true\n'
          'language: "es"\n'
          'date_processed: "2026-08-12"\n'
          'tags: []\n'
          '---\n\n'
          '<!-- pagina 1 -->\n'
          '# Titulo del documento\n\n'
          '## Introduccion\n'
          'Texto del documento...\n\n'
          '| Nombre | Edad | Ciudad |\n'
          '| --- | --- | --- |\n'
          '| Juan | 25 | Santo Domingo |')
S += P(f"Los comentarios {k('<!-- pagina N -->')} son invisibles al leer, pero permiten citar "
       "la p&aacute;gina de origen m&aacute;s adelante.")

# ---- 9 ----
S += H1("9. Configuraci\u00f3n (config.yaml)")
S += P("Todos los valores son opcionales. Los m&aacute;s &uacute;tiles:")
S += TABLE([["Opci&oacute;n", "Para qu&eacute; sirve"],
            [k("output_dir"), "Carpeta donde se guardan los .md"],
            [k("ocr_lang"), "Idioma del OCR (spa, o spa+eng para mixto)"],
            [k("ocr_dpi"), "Resoluci&oacute;n del OCR (200-400; m&aacute;s alto = mejor pero m&aacute;s lento)"],
            [k("detect_tables"), "Activar/desactivar la detecci&oacute;n de tablas"],
            [k("include_page_markers"), "Insertar las marcas de p&aacute;gina"],
            [k("watch_dir"), "Carpeta de ENTRADA del modo autom&aacute;tico"],
            [k("vault_dir"), "Carpeta de tu b&oacute;veda de Obsidian (null = desactivado)"],
            [k("vault_subdir"), "Subcarpeta dentro de la b&oacute;veda ('PDF importados')"],
            [k("auto_relate"), "En la vigilancia, conectar las notas autom&aacute;ticamente tras organizar"],
            [k("relate_threshold"), "Confianza m&iacute;nima para crear un enlace (0-1; m&aacute;s alto = menos enlaces)"],
            [k("relate_top_k"), "M&aacute;ximo de enlaces por nota (evita saturar el grafo)"]],
           [150, CONTENT_W - 150])

# ---- 10 ----
S += H1("10. C\u00f3mo funciona por dentro")
S += P("El coraz&oacute;n del dise&ntilde;o es un <b>modelo com&uacute;n</b>: sin importar el formato de "
       "entrada, cada documento se convierte en una lista de p&aacute;ginas y bloques (t&iacute;tulo, "
       "p&aacute;rrafo, lista o tabla). Todo lo dem&aacute;s opera sobre esa estructura; por eso a&ntilde;adir "
       "Word y Excel no oblig&oacute; a reescribir nada.")
S += CODE("Entrada (PDF / Word / Excel)\n"
          "        |\n"
          "        v\n"
          "  convert_file()      <- despachador: elige el lector por extension\n"
          "        |\n"
          "   +----+----+-----------+\n"
          "   |         |           |\n"
          " convert_  docx_       xlsx_\n"
          " pdf       extractor   extractor\n"
          "   |         |           |\n"
          "   +----+----+-----------+\n"
          "        v\n"
          "  DocumentResult  (paginas -> bloques)\n"
          "        |\n"
          "        v\n"
          "  markdown_writer  -> archivo .md (metadatos + contenido)\n"
          "        |\n"
          "        v\n"
          "  vault.py  -> boveda de Obsidian (+ indice)")
S += TABLE([["Archivo", "Responsabilidad"],
            [k("pipeline.py"), "Orquesta y procesa por lotes; despachador convert_file"],
            [k("docx_extractor.py"), "Lee Word"],
            [k("xlsx_extractor.py"), "Lee Excel"],
            [k("text_extractor.py") + " / " + k("ocr.py"), "Leen PDF digital / escaneado"],
            [k("cleaning.py"), "Limpia y normaliza (sin inventar)"],
            [k("markdown_writer.py"), "Bloques a Markdown + metadatos"],
            [k("vault.py"), "Publica y organiza la b&oacute;veda de Obsidian"],
            [k("semantics/"), "Conecta las notas por significado (Fase 2.6)"],
            [k("config.py") + " / " + k("errors.py"), "Configuraci&oacute;n / errores y registro"]],
           [175, CONTENT_W - 175])

# ---- 11 ----
S += H1("11. Errores y soluci\u00f3n de problemas")
S += H2("C\u00f3mo maneja los errores")
S += P("Cada archivo se procesa aislado: si uno falla, el lote contin&uacute;a. Los fallos se "
       f"guardan en {k('documentos/errores/')} (un &iacute;ndice, la traza completa y avisos no "
       "fatales como baja confianza del OCR). En el modo autom&aacute;tico, el archivo que falla se "
       "mueve a esa carpeta.")
S += H2("Problemas comunes")
S += TABLE([["S&iacute;ntoma", "Causa y soluci&oacute;n"],
            ["'Falta la librer&iacute;a python-docx / openpyxl'",
             f"Ejecutas con un Python que no tiene esa librer&iacute;a. Instala con "
             f"{k('pip install -r requirements.txt')} en el <b>mismo</b> Python que usan tus .bat."],
            ["Un Word/Excel fall&oacute; y se fue a 'errores'",
             "Corrige la causa (normalmente lo anterior) y vuelve a arrastrar el archivo a la "
             "carpeta de entrada para reprocesarlo."],
            ["Un PDF escaneado no se convierte",
             f"Falta Tesseract o el idioma. Revisa {k('tesseract_cmd')} en config.yaml. Las "
             "p&aacute;ginas quedan marcadas como pendientes; el lote no se detiene."],
            ["Borr&eacute; los .md sin querer",
             f"Est&aacute;n en la Papelera de reciclaje; o regen&eacute;ralos: los originales quedan en "
             f"{k('documentos/procesados/')}, vuelve a convertirlos."]],
           [150, CONTENT_W - 150])

# ---- 12 ----
S += H1("12. Limitaciones conocidas")
S += UL(["La detecci&oacute;n de t&iacute;tulos es heur&iacute;stica: muy buena en documentos regulares, "
         "mejorable en dise&ntilde;os complejos (multicolumna, formularios).",
         "Las <b>tablas sin l&iacute;neas</b> (facturas alineadas por espacios) quedan como texto: "
         "el contenido se conserva, pero no la rejilla.",
         "Bloques de firma o negrita centrada pueden marcarse como t&iacute;tulos por error.",
         "No hay detecci&oacute;n de tablas en PDF escaneados (reconstruir la rejilla es fr&aacute;gil).",
         "Un Excel muy grande se recorta a 5000 filas por hoja (l&iacute;mite de seguridad)."])

# ---- 13 ----
S += H1("13. Roadmap (pr\u00f3ximas fases)")
S += UL(["<b><font color='#0f6e56'>Hecho &mdash; Fase 1:</font></b> conversi&oacute;n de PDF, Word y Excel a Markdown.",
         "<b><font color='#0f6e56'>Hecho &mdash; Fase 2:</font></b> publicaci&oacute;n en Obsidian, con &iacute;ndice y organizaci&oacute;n por formato.",
         "<b><font color='#0f6e56'>Hecho &mdash; Fase 2.6:</font></b> relaciones sem&aacute;nticas: mapas por tema; las notas se conectan por significado.",
         "<b>Fase 2.5:</b> exportar de vuelta a PDF (de la b&oacute;veda a un PDF limpio).",
         "<b>Fase 3 (RAG):</b> trocear el texto, generar 'embeddings' y una base vectorial.",
         "<b>Fase 4 (RAG):</b> el chatbot que responde citando la p&aacute;gina de origen."])


def on_page(canvas, doc):
    if doc.page > 1:
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(A4[0] / 2, 12 * mm, str(doc.page))
        canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=18 * mm, bottomMargin=20 * mm,
                        title="Documentacion - PDF, Word y Excel a Markdown",
                        author="Giovy Polanco")
doc.build(S, onFirstPage=on_page, onLaterPages=on_page)
print("PDF generado:", OUT)
