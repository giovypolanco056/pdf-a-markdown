# Relaciones semánticas entre notas (Fase 2.6)

> Convierte tu carpeta de Markdown en una base de conocimiento **conectada**:
> el sistema lee el contenido de cada nota, descubre de qué habla y la enlaza
> con las notas relacionadas —por **tema, proyecto, entidad o evento**— aunque
> no usen exactamente las mismas palabras. Markdown sigue siendo la fuente de
> verdad; Obsidian es la capa de exploración.
>
> **Prioridad: precisión > cantidad.** Mejor pocas relaciones buenas que un
> grafo lleno de conexiones inútiles.

---

## 1. Qué hace, en una frase

Después de convertir y publicar tus documentos en la bóveda, ejecutas
`relacionar.py` (o lo activas en el modo vigilancia) y el sistema:

1. Analiza el contenido de cada nota.
2. Detecta **conceptos**, **entidades**, **tipo de evento** y **palabras clave**.
3. Calcula un **nivel de confianza** para cada par de notas.
4. Sólo cuando la confianza supera un umbral, crea el enlace.
5. Escribe en cada nota: tags (`tema/…`, `evento/…`, `entidad/…`), `keywords`,
   la propiedad `related` y una sección **🔗 Notas relacionadas** con los enlaces
   y su porcentaje de confianza.
6. Crea mapas por tema (`Tema - X.md`) y un `Mapa de Temas.md`, que son los
   nodos-hub del grafo.

Todo esto es **no destructivo**: sólo se reescribe el front matter y una sección
delimitada por marcadores; nunca se toca el texto convertido.

---

## 2. Cómo se integra (sin romper lo existente)

El proyecto ya tenía tres capas. La semántica es una **cuarta capa** que se
añade al final, análoga a `organizar_boveda`:

```
convert_file()        → .md en output_dir              (conversión, Fase 1)
publish_markdown_file → copia a la bóveda + front matter (publicación, Fase 2)
organizar_boveda()    → agrupa por FORMATO (origen/pdf…) (organización, Fase 2)
relacionar_boveda()   → relaciona por SIGNIFICADO        (semántica, Fase 2.6)  ← NUEVO
```

Cada capa gobierna su **propio namespace de tags** para no pisarse:

| Capa | Namespace de tags | Mapas que crea |
|---|---|---|
| Organización | `origen/pdf`, `origen/word`, `origen/excel` | `Mapa - PDF/Word/Excel`, `Índice` |
| Semántica | `tema/…`, `evento/…`, `entidad/…` | `Tema - X`, `Mapa de Temas` |

`organizar_boveda` se ajustó para (a) re-sellar **sólo** sus tags `origen/`
(antes borraba también `tema/`) y (b) ignorar los mapas de tema. Así puedes
re-organizar por formato sin perder las relaciones, y viceversa.

**Componentes nuevos** (todos bajo `src/pdf2md/semantics/`):

| Archivo | Responsabilidad |
|---|---|
| `normalize.py` | Tokenización en español: minúsculas, sin acentos, stopwords, *stemming* ligero, n-gramas. |
| `lexicon.py` | Carga `conceptos.yaml`; detecta conceptos y eventos; **jerarquía de conceptos**. |
| `entities.py` | Extrae siglas, códigos/expedientes, fechas y nombres propios. |
| `profile.py` | Perfil por nota + **índice auxiliar incremental** (`_semantica.json`). |
| `relate.py` | TF-IDF + coseno, **score de confianza**, y escritura en Obsidian. |
| `embeddings.py` | Backend **opcional** de embeddings (tras el contrato `BaseEmbedder` del RAG). |
| `data/conceptos.yaml` | **El conocimiento del dominio** (datos, no código). |

Componentes modificados: `config.py`, `config.yaml` (opciones nuevas),
`vault.py` (namespaces), `watch.py` (relacionar tras organizar si `auto_relate`).
Nada del pipeline de conversión cambió.

---

## 3. Cómo funciona el análisis semántico (los 7 niveles)

No es `if "hidrobombeo" in texto`. Son **siete señales** que se combinan en un
único score. Cada una cubre uno de los niveles de detección que pediste:

| # | Señal | Cómo se calcula | Peso |
|---|---|---|---|
| 1-2 | **Texto / palabras clave** | TF-IDF (frecuencia ponderada por rareza) + similitud de coseno. Las palabras comunes pesan poco; las distintivas, mucho. | 0.38 |
| 3 | **Tema / sinónimos** | Léxico de conceptos con **jerarquía padre** (ver abajo). Coseno de los vectores de concepto. | 0.34 |
| 5 | **Entidades compartidas** | Siglas, códigos, fechas y nombres comunes a dos notas, ponderados por rareza. | 0.18 |
| 7 | **Tipo de evento** | Reunión, informe, incidente, proyecto… | 0.05 |
| 6 | **Temporal** | Documentos con fechas próximas (de su nombre o su texto, no la de proceso). | 0.05 |
| 5b | **Similitud semántica** (opcional) | Embeddings de un modelo de lenguaje. | (extra) |

> **Confianza = suma ponderada de las señales, en el rango 0–1.**

### El puente semántico (lo que resuelve tu ejemplo del hidrobombeo)

Los conceptos se organizan en un **árbol**. En `conceptos.yaml`:

```
energia
├── hidroelectrica
│   └── hidrobombeo
└── almacenamiento-energetico
```

Cuando una nota activa un concepto, ese peso **irradia hacia sus padres**
(mitad por nivel). Así:

* Una nota que sólo dice *"planta de bombeo"* → activa `hidrobombeo` → irradia a
  `hidroelectrica` y a `energia`.
* Otra que sólo dice *"almacenamiento energético mediante agua"* → activa
  `almacenamiento-energetico` → irradia a `energia`.

**Ambas se encuentran en el nodo `energia`**, aunque no compartan ni una palabra.
Ése es el puente que detecta relaciones por significado sin necesidad de IA.

### La regla de corroboración (evita relaciones falsas)

Las señales de **evento** y **fecha** son de apoyo: por sí solas **nunca** crean
un enlace. Si dos notas sólo coinciden en "ser informes" o "ser de fechas
cercanas", pero no comparten tema, entidad ni texto, **no se relacionan**. Esto
es exactamente tu caso: `Proyecto A ↔ Recursos Humanos` con 21 % se descarta.

---

## 4. Formato de Markdown y front matter

Cada nota conserva su estructura original y gana estos campos (ejemplo real):

```yaml
---
title: "Proyecto de Hidrobombeo Valle Nuevo"
source: "2026-08-01-Proyecto-Hidrobombeo.pdf"
file_type: "pdf"
# … (campos del conversor, intactos) …
tags:
  - "pdf-importado"
  - "origen/pdf"                             # capa de formato
  - "tema/energia"                           # capa semántica ↓
  - "tema/energia/hidrobombeo"
  - "tema/energia/almacenamiento-energetico"
  - "evento/proyecto"
  - "entidad/egehid"
keywords: [hidrobombeo, central, embalse, turbinas, egehid, cronograma]
conceptos: ["Hidrobombeo", "Energía hidroeléctrica", "Almacenamiento energético"]
entidades: ["EGEHID"]
related:
  - "[[2026-08-10-Informe-Proyecto]]"
  - "[[2026-08-05-Central-Bombeo]]"
---

<!-- … el contenido convertido, intacto … -->

<!-- relaciones:inicio -->
## 🔗 Notas relacionadas

> Detectadas automáticamente. El porcentaje es el nivel de confianza.

- [[2026-08-10-Informe-Proyecto|Informe de avance del proyecto]] — **52%** · tema, entidad, texto, fecha
- [[2026-08-05-Central-Bombeo|Central de bombeo del río Blanco]] — **40%** · tema, texto, fecha
<!-- relaciones:fin -->
```

**Por qué así:**

* Los **tags jerárquicos** (`tema/energia/hidrobombeo`) crean un árbol navegable
  en el panel de tags de Obsidian.
* La sección **🔗 Notas relacionadas** usa `[[wikilinks]]` en el **cuerpo**, que
  es lo más fiable para el **Graph View** y los **Backlinks**.
* La propiedad **`related`** duplica los enlaces en el panel de Propiedades.
* Los marcadores `<!-- relaciones:inicio/fin -->` permiten **regenerar** esa
  sección sin tocar nada más (idempotencia).

---

## 5. Cómo se ve en Obsidian

| Función de Obsidian | Qué muestra |
|---|---|
| **Graph View** | Las notas de un mismo tema forman un racimo; los `Tema - X` son nodos-hub grandes. La nota fuera de tema queda aislada. |
| **Tags** (panel) | Árbol `tema → energia → hidrobombeo`, `evento`, `entidad`, `origen`. |
| **Backlinks** | Cada nota ve quién la menciona. |
| **Propiedades** | `keywords`, `conceptos`, `entidades`, `related`. |
| **`Mapa de Temas.md`** | Índice de todos los temas detectados (ábrelo primero). |
| **`Tema - X.md`** | Todas las notas de un tema, como un MOC. |

Consejo: en Ajustes → *Core plugins* → *Graph view*, colorea por tag `tema/*`
para ver los grupos temáticos de un vistazo.

---

## 6. Cómo se controla la precisión

Cuatro mecanismos, todos configurables:

1. **Umbral de confianza** (`relate_threshold`, por defecto 0.22). Súbelo para
   menos enlaces pero más seguros.
2. **Tope por nota** (`relate_top_k`, por defecto 6). Aunque una nota tenga 20
   candidatas, sólo se quedan las 6 mejores.
3. **Regla de corroboración** (código): evento/fecha no enlazan solos.
4. **Léxico curado** (`conceptos.yaml`): se evitan palabras ambiguas ("activo",
   "personal", "artículo"…) y se prefieren **frases distintivas**, que además
   pesan más que las palabras sueltas.

Cada ejecución escribe **`_relaciones.md`**, una auditoría legible con cada nota,
sus conceptos y sus relaciones con el porcentaje y las señales que las sostienen.
Úsala para verificar que no hay relaciones falsas o excesivas.

---

## 7. Cómo mantenerlo actualizado

* **Al agregar notas nuevas:** vuelve a ejecutar `relacionar.py`. Gracias al
  índice `_semantica.json` (con un hash del contenido), sólo se **re-analizan las
  notas que cambiaron**; el resto se reutiliza. Si editas `conceptos.yaml` o se
  actualiza la lógica, el índice se invalida solo y se recalcula todo.
* **Automático:** pon `auto_relate: true` en `config.yaml` y, en el modo
  vigilancia, cada archivo nuevo se convertirá, publicará, organizará **y
  relacionará** sin que toques nada.
* **Idempotente:** ejecutarlo dos veces sin cambios no reescribe nada.

---

## 8. Uso

```bash
# Con las rutas de config.yaml (vault_dir):
python relacionar.py

# O apuntando a una bóveda concreta y ajustando el umbral:
python relacionar.py -d "C:\ruta\a\tu\Boveda" --threshold 0.25 --top-k 5
```

O doble clic en **`relacionar.bat`**. Opciones en `config.yaml`:

```yaml
auto_relate: false        # relacionar automáticamente en el modo vigilancia
relate_threshold: 0.22    # confianza mínima (0-1)
relate_top_k: 6           # máx. enlaces por nota
relate_keywords: 8        # nº de keywords por nota
relate_lexicon: null      # ruta a tu propio conceptos.yaml (null = el de serie)
```

---

## 9. Ampliar el conocimiento del dominio

El sistema crece **editando datos, no código**. Abre
`src/pdf2md/semantics/data/conceptos.yaml` y añade un concepto:

```yaml
  mantenimiento-turbinas:
    label: "Mantenimiento de turbinas"
    padre: hidroelectrica          # hereda el puente hacia energia
    terminos:
      - mantenimiento de turbina
      - cambio de rodete
      - overhaul de la unidad
```

Consejos para no perder precisión:

* Prefiere **frases** ("ciclo contable") a palabras sueltas ("activo").
* Evita términos que aparezcan en muchos contextos distintos.
* Usa `padre:` para conectar un concepto específico con su familia.

Tras editar, ejecuta `relacionar.py`: el índice se recalcula automáticamente.

---

## 10. Embeddings (opcional, vía de crecimiento)

El motor funciona **sin** modelos de lenguaje. Si algún día quieres una señal de
similitud semántica "de verdad", el sistema ya tiene el enganche
(`embeddings.py`, implementando el `BaseEmbedder` que estaba esbozado para el
RAG). Requiere instalar `sentence-transformers`, que **hoy no tiene versión para
Python 3.14** (tu entorno). Cuando lo tenga:

```yaml
relate_use_embeddings: true
relate_embed_model: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
relate_embed_weight: 0.40
```

Si el modelo no está disponible, el sistema lo detecta y sigue con las señales
sin-dependencias, sin romperse.

---

## 11. Pruebas

`tests/test_semantics.py` (ejecútalo con `python tests/test_semantics.py`)
verifica lo esencial:

* el **puente por concepto padre** relaciona notas sin palabras comunes,
* una nota **fuera de tema no se relaciona** (precisión),
* se generan los **mapas de tema** y la **sección de relaciones**,
* el proceso es **idempotente e incremental**.
```
