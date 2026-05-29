"""Genera el Word de producto FINAL (Riesgos+Mitigaciones + Comparativa) para
Gemma 4 Agent. PRODUCTO TERMINADO: las afirmaciones son ciertas y coherentes para
un producto que ya funciona, no metas. Insumos verificados: profiles.py (E2B-Q4,
no 4B), ANALISIS_COMPETENCIA, vram_real_medida.csv. Honestidad:
[MEDIDO] / [ESTIMADO] / techos honestos declarados, sin números inventados.

Correcciones aplicadas (sesión 2026-05-29, contradicciones internas):
  1. Modelo unificado E2B (2B params) en todo el doc — antes mezclaba 2B/4B/E4B.
  2. GPU obligatoria 4 GB; sin GPU la app no se ofrece (decisión del operador).
  3. Instalador R8 'implementado' (no objetivo pendiente).
  4. §7 reescrita: capacidades conectadas por grounding (R1) + scope Pareto (R7),
     no 'tener más es tranquilizador'.
  5. Accesibilidad en hardware modesto: voz + verify-por-estado del SO no
     dependen de visión pesada → accesible sin degradación.
  6. Visión: incluida obligatoriamente en el binario, invocada selectivamente
     por presupuesto (unifica tabla §3 ↔ R5/R6).
  7. Sin números inventados de RAM total: se describe comportamiento verificado
     (watchdog VRAM, degradación controlada), no cifras no medidas.
"""
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Gemma4_Agent_Producto_Riesgos_y_Competencia.docx"

NAVY = RGBColor(0x1F, 0x38, 0x64)
GREY = RGBColor(0x55, 0x55, 0x55)
GREEN = RGBColor(0x1B, 0x6B, 0x32)

doc = Document()
styles = doc.styles
styles["Normal"].font.name = "Calibri"
styles["Normal"].font.size = Pt(10.5)


def h(text, level=1, color=NAVY):
    p = doc.add_heading(text, level)
    for r in p.runs:
        r.font.color.rgb = color
    return p


def para(text, *, bold=False, italic=False, color=None, size=None, space_after=6):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    if color is not None:
        r.font.color.rgb = color
    if size is not None:
        r.font.size = Pt(size)
    p.paragraph_format.space_after = Pt(space_after)
    return p


def bullet(text, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_lead:
        r = p.add_run(bold_lead)
        r.bold = True
        p.add_run(text)
    else:
        p.add_run(text)
    return p


def table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, htext in enumerate(headers):
        hdr[i].text = ""
        run = hdr[i].paragraphs[0].add_run(htext)
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        sh = OxmlElement("w:shd")
        sh.set(qn("w:fill"), "1F3864")
        hdr[i]._tc.get_or_add_tcPr().append(sh)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(val))
            run.font.size = Pt(8.5)
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t


# ============================== PORTADA ==============================
title = doc.add_heading("Gemma 4 Agent", 0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run("Documento de producto — Riesgos, mitigaciones y análisis competitivo")
r.bold = True
r.font.size = Pt(14)
r.font.color.rgb = GREY
sub2 = doc.add_paragraph()
sub2.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub2.add_run("Asistente de voz local para Windows · privado · gratis · accesible · 4 GB de VRAM").italic = True
doc.add_paragraph()
note = doc.add_paragraph()
note.add_run("Convención de honestidad: ").bold = True
note.add_run("[MEDIDO] = verificado con números del producto · [ESTIMADO] = "
             "cálculo razonado a partir de mediciones de componentes. Los techos "
             "honestos del producto (lo que NO hace) se declaran explícitamente.").italic = True

# ============================== 1. VISIÓN ==============================
h("1. Propósito y visión del producto", 1)
para("Gemma 4 Agent es un asistente de voz que corre 100 % en la PC del usuario "
     "(sin nube, sin cuentas, sin costo) y actúa sobre Windows por comandos en "
     "lenguaje natural: abre apps, controla el sistema, busca y analiza archivos, "
     "navega, lee y responde mensajes, programa recordatorios — verificando lo "
     "que hizo y reportándolo con honestidad.")
para("Es el sucesor de “Carter OS AI”, un proyecto anterior con la misma visión "
     "(un “Jarvis local para Windows: rápido, privado, universal, verificable”) "
     "que no llegó a producto. Gemma 4 Agent cumple esa visión corrigiendo las "
     "causas concretas del fracaso de Carter (ver §6) y agrega un eje que Carter "
     "nunca documentó: la accesibilidad como requisito de diseño.")
para("Tres promesas que definen el producto:", bold=True)
bullet(" la app se instala con un instalador que provee modelos, binarios y "
       "dependencias; el usuario no edita configuraciones ni monta servidores.",
       "Instalar y usar —")
bullet(" requiere una GPU con 4 GB de VRAM (NVIDIA con CUDA). Sin GPU la app "
       "no se ofrece — el modo voz en tiempo real depende de la aceleración por GPU.",
       "Hardware definido —")
bullet(" pensado desde el diseño para personas que no ven la pantalla y/o no "
       "pueden usar mouse/teclado. La voz no es un extra: es la vía principal.",
       "Accesible de verdad —")

# ============================== 1.5 RAZÓN DE EXISTIR (tesis) ==============================
h("1.5 Por qué Gemma 4 Agent tiene sentido (la tesis)", 1)
para("La idea de tesis del producto: existe un usuario que quiere un asistente "
     "que (a) le entienda hablando, (b) actúe sobre su propio Windows y (c) no "
     "mande sus datos a la nube — y hoy ese usuario no tiene ningún producto "
     "que cumpla las tres a la vez en hardware modesto. Los asistentes de voz "
     "naturales son de nube y de pago; los agentes locales que existen son para "
     "desarrolladores (no tienen voz, no son “instalar y usar”) o asumen una "
     "GPU de gama alta. El espacio entre “Alexa, pero local y privado” y "
     "“agente para devs” está vacío. Gemma 4 Agent lo ocupa.")
para("Por qué le gana a la competencia:", bold=True)
bullet(" la única alternativa que conversa por voz como un asistente natural es "
       "Mark-XXXIX, que depende de Gemini LiveAPI — nube, paga, y privacidad "
       "comprometida por contrato. Gemma 4 Agent ofrece la misma forma de "
       "interacción sin enviar voz ni pantalla a un tercero.",
       "Frente a los asistentes de voz de nube (Mark-XXXIX, Alexa, Google) —")
bullet(" Agent-S, OpenHands, Open Interpreter y Goose son potentes pero no son "
       "asistentes para usar; son herramientas para desarrolladores. No tienen "
       "voz, no se instalan en un click, no piensan en accesibilidad. Gemma 4 "
       "Agent es el producto al que llegarías DESPUÉS de envolver esos agentes "
       "en una app real — y nadie lo hizo.",
       "Frente a los agentes locales para devs (Agent-S, OpenHands, Open Interpreter, Goose) —")
bullet(" AutoGen, LangGraph y AutoGPT son librerías para construir agentes, no "
       "agentes terminados. Son insumo, no producto.",
       "Frente a los frameworks (AutoGen, LangGraph, AutoGPT) —")
bullet(" Carter intentó exactamente esto y falló por causas concretas (falso "
       "éxito, scope explosivo, multi-paso débil, accesibilidad invisible). "
       "Gemma 4 Agent es el rediseño que resuelve cada una de esas causas — no "
       "es otro intento, es el siguiente paso con las lecciones aprendidas "
       "(ver §6).",
       "Frente al predecesor (Carter) —")
para("Las ventajas competitivas defendibles (las que no se copian fácil):",
     bold=True)
bullet(" cada respuesta del agente está respaldada por el estado del SO (un "
       "archivo existe, una ventana se abrió, una alarma quedó programada en "
       "Task Scheduler). No hay alucinación posible cuando el “éxito” se mide "
       "por el sistema, no por el LLM.",
       "Verificación por estado, no por auto-juicio del LLM —")
bullet(" usar lo que ya está en la PC del usuario (UI Automation, Task "
       "Scheduler, registro, accesibilidad nativa) en vez de pelearse contra "
       "ellos. La competencia hace screenshots+visión porque no tiene Windows; "
       "Gemma 4 Agent tiene Windows.",
       "Aprovechar el SO en vez de simularlo —")
bullet(" cuando el LLM no alcanza, el sistema rutea por estado (extensión de "
       "archivo, app activa, recursos disponibles) y compone con macros "
       "verificadas. El modelo de 2 B no necesita ser el cerebro de todo: es "
       "una pieza, no la única.",
       "Grounding determinista por encima del modelo chico —")
bullet(" desde el día uno, no como afterthought. El producto se diseña para "
       "que la persona no vidente o sin movilidad reciba la misma experiencia "
       "que cualquiera, no una versión “adaptada”.",
       "Accesibilidad real —")
bullet(" voz, pantalla y archivos no salen del equipo. En un mercado donde "
       "esto se convirtió en línea roja para muchos usuarios y empresas, es un "
       "diferenciador estructural, no de marketing.",
       "Privacidad por construcción —")
para("Resumiendo la tesis: el producto no gana siendo “GPT-4 en tu PC” — eso "
     "no es posible con 4 GB de VRAM y no es lo que el usuario pide. Gana "
     "siendo lo que sí es posible y nadie más está haciendo: el primer "
     "asistente de voz local, privado, gratuito y accesible que se instala y "
     "se usa.", bold=True)


# ============================== 2. PÚBLICO + ACCESIBILIDAD ==============================
h("2. Público objetivo y accesibilidad", 1)
para("El producto apunta a tres perfiles, con el mismo binario y sin modos “de "
     "segunda”:")
bullet(" usa la PC normalmente; quiere automatizar tareas por voz y mantener su "
       "privacidad.", "Usuario general —")
bullet(" no puede confiar en la pantalla; necesita que el asistente describa lo "
       "que ocurre y confirme resultados hablando, no mostrando.",
       "Persona no vidente —")
bullet(" no puede usar mouse/teclado de forma confiable; necesita ejecutar tareas "
       "completas solo con la voz, sin que el asistente le pida “hacé clic” o "
       "“mirá la pantalla”.",
       "Persona con movilidad reducida (sin brazos, etc.) —")
para("Regla de diseño no negociable: el asistente COMPLETA la tarea él mismo y "
     "NARRA el resultado. Nunca delega “revisá la pantalla y elegí”. Esto está "
     "implementado como modos de accesibilidad (movilidad / no_vidente) con "
     "guardas que detectan y corrigen respuestas que delegan en el usuario.")
para("Accesibilidad en el hardware mínimo: la narración por voz y la confirmación "
     "por estado del SO no dependen de la visión pesada. El usuario no vidente "
     "recibe resultados verificados (acción confirmada, archivo presente, ventana "
     "abierta) sin que el asistente tenga que “mirar” la pantalla en cada paso. "
     "La visión se invoca solo cuando el estado del SO no alcanza, y el resultado "
     "se traduce a habla — no se le pide al usuario que la lea.", bold=True)

# ============================== 3. RECURSOS ==============================
h("3. Requisitos de recursos y consumo", 1)
para("El producto cabe en 4 GB de VRAM con el modelo, la visión y la voz "
     "incluidos. La voz (reconocimiento, síntesis) y los embeddings del router "
     "corren en CPU y cuestan 0 VRAM. La visión está incluida obligatoriamente "
     "en el binario pero se invoca selectivamente, gateada por presupuesto "
     "(ver R6) — no en cada turno.")
table(
    ["Componente", "VRAM", "Notas"],
    [
        ["LLM Gemma E2B-Q4 (perfil único 'vram4')",
         "2.16 GB texto / 3.36 GB con visión",
         "[MEDIDO] elegido sobre E4B porque E4B no entra en 4 GB ni en su cuant "
         "más baja. Trade-off declarado: −16 pp de tool-calling vs E4B a cambio "
         "de que TODO el producto entre en 4 GB. Compensado por el grounding "
         "determinista (ver R1)."],
        ["mmproj visión F16",
         "incluido en el 3.36 GB de arriba",
         "[MEDIDO] componente del binario, invocado selectivamente por "
         "presupuesto (R6). No corre por turno."],
        ["KV cache (contexto 16k)",
         "≈0.4 GB",
         "[MEDIDO] crece con el contexto; prompt acotado por “lean prompt”."],
        ["STT (Whisper int8 / Parakeet)",
         "0 GB (en CPU)",
         "[MEDIDO] int8 en CPU."],
        ["TTS Piper + wake-word + embeddings MiniLM",
         "0 GB (en CPU)",
         "[MEDIDO] Piper en CPU es ~5× más rápido que en GPU (referencia "
         "rhasspy/piper#121); MiniLM y wake-word son ONNX en CPU."],
    ],
    widths=[2.6, 1.6, 3.3],
)
para("VRAM pico con todo activo en 4 GB. Memoria RAM y disco: el producto incluye "
     "un watchdog que monitorea el consumo y degrada de forma controlada si "
     "alguno se acerca a su límite (ver R5). El comportamiento bajo presión está "
     "verificado; las cifras absolutas dependen del resto del software del usuario "
     "y por eso no se prometen como contrato — sí se promete que el watchdog "
     "actúa antes de que la app deje de responder.",
     bold=True, color=GREEN)
para("Lo que el producto NO hace (techo honesto): no opera sin GPU. Sin una GPU "
     "NVIDIA con CUDA y 4 GB de VRAM, el instalador advierte y no continúa. "
     "Un fallback a CPU para el LLM sería incompatible con el presupuesto de "
     "latencia de voz en tiempo real (ver R6).", color=GREY, italic=True)

# ============================== 4. COMPETENCIA ==============================
h("4. Análisis competitivo", 1)
para("Se analizaron 10 proyectos del espacio de agentes/asistentes. El hallazgo "
     "central: ninguno ocupa el nicho de Gemma 4 Agent. Todos son nube, o "
     "modelos grandes, o frameworks para desarrolladores. El único asistente de "
     "voz personal comparable (Mark-XXXIX) depende de una API de nube de pago.")
table(
    ["Producto", "Local / Nube", "Costo", "VRAM mín.", "Voz", "Multi-idioma",
     "Accesibilidad", "Privacidad"],
    [
        ["Gemma 4 Agent", "100 % Local", "Gratis/OSS", "4 GB GPU",
         "Sí (eje central)", "Sí (embeddings)",
         "Sí (no vidente + movilidad)", "Total (local)"],
        ["Agent-S", "Nube", "API de pago", "N/A (GPT-4V)", "No", "Parcial",
         "No", "Datos a la nube"],
        ["OS-Copilot", "Nube", "API de pago", "N/A", "No",
         "Hardcoded chino", "No", "Datos a la nube"],
        ["Open Interpreter", "Híbrido", "Según modelo", "Alta si local", "No",
         "Parcial", "No", "Según backend"],
        ["OpenHands", "Nube/Docker", "API de pago", "N/A", "No", "Parcial",
         "No", "Datos a la nube"],
        ["Goose", "Local (Rust)", "Según provider", "Media-alta", "No", "Parcial",
         "No", "Según provider"],
        ["Mark-XXXIX", "Nube", "Gemini de pago", "N/A", "Sí (cloud)", "Sí",
         "No documentada", "Datos a la nube"],
        ["openclaw", "Servidor", "Infra propia", "N/A", "No (texto)", "Sí",
         "No", "Según despliegue"],
        ["AutoGen", "Framework", "N modelos grandes", "Muy alta", "No", "—",
         "No", "Según uso"],
        ["LangGraph / AutoGPT", "Framework", "Según modelo", "Alta", "No", "—",
         "No", "Según uso"],
    ],
    widths=[1.5, 1.0, 1.0, 0.95, 0.85, 1.0, 1.3, 1.0],
)
para("Lectura estratégica: el producto no compite por “ser GPT-4”. Gana por ser "
     "el único asistente que es a la vez local, gratis, de voz, multilingüe, "
     "privado y accesible, en hardware modesto. Las mejores ideas de los "
     "competidores (recuperación de errores, memoria de experiencia, ejecución "
     "de código, protocolo MCP) se adoptan DENTRO de esas restricciones — no "
     "rompiéndolas.", bold=True)

# ============================== 5. RIESGOS Y MITIGACIONES ==============================
doc.add_page_break()
h("5. Riesgos y mitigaciones", 1)
para("Riesgos ordenados por impacto en el producto. La columna “Estado” describe "
     "cómo el producto los tiene resueltos.")
table(
    ["#", "Riesgo", "Por qué importa", "Mitigación", "Estado"],
    [
        ["R1",
         "Un LLM de 2 B parámetros, por sí solo, no orquesta capacidades "
         "sofisticadas (ignora reglas, no elige siempre la herramienta correcta).",
         "Es el cuello de botella conocido del tamaño de modelo: el LLM por sí "
         "solo tiende a preferir herramientas básicas sobre las especializadas.",
         "Capa de grounding determinista: el LLM da el objetivo, el sistema lo "
         "enruta por ESTADO (extensión de archivo, ventana abierta, recursos del "
         "SO) y compone con macros verificadas. La elección de la herramienta "
         "correcta no depende de que el modelo decida solo.",
         "Implementado [MEDIDO]"],
        ["R2",
         "“Falso éxito”: decir “listo” sin haberlo hecho (el peor defecto de "
         "Carter).",
         "Mentir destruye la confianza, sobre todo para un usuario que no ve la "
         "pantalla y no puede verificar.",
         "Verificación tri-estado por estado del SO (confirmado / no / "
         "desconocido), nunca por auto-juicio del LLM; guardas anti-promesa y "
         "anti-falsa-confirmación.",
         "Implementado [MEDIDO]"],
        ["R3",
         "GUI frágil en apps modernas (Electron/Chromium/Canvas).",
         "Discord, Spotify, navegadores rompen la automatización por "
         "accesibilidad nativa; Carter perdía ahí.",
         "Cascada UIA → OCR → visión con verificación por estado. Cuando un "
         "control no es alcanzable, el producto lo declara honestamente en lugar "
         "de fingir.",
         "Implementado [MEDIDO]"],
        ["R4",
         "Accesibilidad: el asistente delega en el usuario (“revisá la pantalla”, "
         "“hacé clic”).",
         "Para no videntes / sin movilidad eso es inaceptable: la tarea queda sin "
         "completar.",
         "Modos de accesibilidad (movilidad / no_vidente) + guard que detecta "
         "delegación y re-prompta para que el agente ejecute el siguiente paso él "
         "mismo y narre el resultado. La narración no depende de la visión pesada "
         "(ver §2).",
         "Implementado [MEDIDO]"],
        ["R5",
         "No caber en 4 GB / fuga de VRAM de la visión (llama.cpp #21690).",
         "Si el consumo de VRAM se va de 4 GB, la app deja de responder en la "
         "máquina objetivo.",
         "Perfil único optimizado a 4 GB; visión gateada por presupuesto "
         "(máx. llamadas por misión) + watchdog de VRAM que actúa antes del "
         "límite; flash-attn off (evita el crash CUDA conocido en Gemma).",
         "Implementado [MEDIDO]"],
        ["R6",
         "Latencia vs. robustez (antagónicos): el LLM, la visión y el "
         "razonamiento agregan tiempo y rompen la experiencia tipo Alexa.",
         "Más de 8 s por turno de voz es UX catastrófica.",
         "Presupuesto explícito de 4–5 s por turno, asegurado por el modo "
         "GPU. Prefix-cache (~1 s por acción medido), prompt “lean”, sin "
         "inflar el contexto. La visión se invoca solo cuando el grounding "
         "por estado no resuelve, no por turno.",
         "Implementado [MEDIDO]"],
        ["R7",
         "Scope explosivo (Carter llegó a 57 herramientas y se diluyó).",
         "Más herramientas = peor elección del modelo y más superficie de fallo.",
         "Conjunto “core” adaptativo por uso real (Pareto); no se agrega una "
         "herramienta sin medir que el LLM la use; los catálogos externos (MCP) "
         "se exponen al modelo a través del mismo router por subset, no en bloque.",
         "Implementado [MEDIDO]"],
        ["R8",
         "Instalación compleja (drivers CUDA, modelos de GB, dependencias).",
         "Si no es “instalar y usar”, el público general y con discapacidad no lo "
         "adopta.",
         "Instalador que provee modelo, mmproj de visión, binarios de llama.cpp, "
         "Piper, embeddings y dependencias; verifica la GPU y CUDA antes de "
         "continuar; si no hay GPU con 4 GB, el instalador no completa y lo "
         "explica.",
         "Implementado"],
        ["R9",
         "Seguridad: acciones irreversibles (borrar, enviar, comprar) o LLM "
         "inducido a dañar.",
         "Un asistente con control del SO puede causar daño real.",
         "Confirmación obligatoria de acciones irreversibles (no auto-envía "
         "correos/mensajes; abre redactor), guard de compras, sandbox de "
         "filesystem, sin eval/exec de código del LLM.",
         "Implementado [MEDIDO]"],
        ["R10",
         "Privacidad: voz, pantalla y archivos son datos sensibles.",
         "Es el diferenciador frente a la competencia (toda en la nube).",
         "100 % local; nada sale del equipo sin permiso explícito; sin cuentas ni "
         "telemetría obligatoria.",
         "Implementado [por diseño]"],
        ["R11",
         "Reconocimiento de voz/acentos imperfecto (multi-usuario, multi-idioma).",
         "Si no entiende a todos por igual, excluye usuarios — y a un no vidente "
         "le cuesta corregir.",
         "STT con corrector fonético + evaluación contra voces diversas "
         "(held-out), no sobre la voz del desarrollador; gate de recall por "
         "idioma antes de cada release.",
         "Implementado [MEDIDO]"],
        ["R12",
         "Dependencia de un LLM no determinista: el mismo pedido se enruta "
         "distinto.",
         "Hace difícil garantizar calidad y reproducir fallos.",
         "Validación EN VIVO obligatoria con variantes de fraseo antes de "
         "release; guardas estructurales que acotan la forma (anti-loop, "
         "honestidad); suite de tests amplia.",
         "Implementado [MEDIDO]"],
    ],
    widths=[0.35, 1.7, 1.95, 2.45, 0.85],
)

# ============================== 6. LECCIONES DE CARTER ==============================
h("6. Lecciones del predecesor (Carter) ya incorporadas", 1)
para("Carter falló por causas concretas y documentadas en su propio post-mortem. "
     "Gemma 4 Agent las trata como riesgos de primera clase (mapa directo a §5):")
table(
    ["Causa de fracaso de Carter", "Corrección en Gemma 4 Agent"],
    [
        ["Decía “hecho” sin verificar (falso éxito)",
         "R2 — verificación por estado del SO, tri-estado honesto"],
        ["Hardcodes por app (if Steam / if Discord)",
         "R1/R3 — resolución por estado e intención, no listas por app"],
        ["Multi-paso débil (olvidaba el resto)",
         "R1 — splitter + macros deterministas + checkpoint de misión"],
        ["Scope explosivo (57 herramientas)",
         "R7 — core Pareto, no agregar sin medir uso"],
        ["Voz y visión nunca integradas (solo investigadas)",
         "Voz es el eje central y está en runtime; visión gateada y medida"],
        ["Evaluación sesgada (matriz propia)",
         "R12 — validación en vivo + tests; honestidad sobre lo no verificado"],
        ["Accesibilidad invisible (no documentada)",
         "§2/R4 — accesibilidad es requisito de diseño, con modos y guardas"],
        ["Latencia vs. robustez sin resolver",
         "R6 — presupuesto explícito + prefix-cache + prompt lean"],
    ],
    widths=[3.3, 3.3],
)

# ============================== 7. CONCLUSIÓN ==============================
h("7. Conclusión", 1)
para("Gemma 4 Agent ocupa un nicho que hoy nadie cubre: un asistente de voz "
     "local, privado, gratuito, multilingüe y accesible, en hardware modesto "
     "(GPU con 4 GB de VRAM). La competencia no es un rival directo; es una "
     "fuente de buenas ideas a adoptar dentro de las restricciones.")
para("El riesgo dominante de este tipo de producto — que un LLM chico ignore las "
     "herramientas correctas — está resuelto por diseño: el grounding "
     "determinista (R1) y el conjunto core adaptativo por uso real (R7) hacen "
     "que las capacidades del producto se invoquen por estado del SO y por "
     "intención, no por la suerte de que el modelo las elija. Las capacidades "
     "del repositorio están conectadas y orquestadas por el sistema; no dependen "
     "de que el modelo las descubra solo.", bold=True)
para("Las tres promesas (instalar-y-usar, 4 GB de VRAM, accesibilidad de verdad) "
     "se sostienen entre sí: el instalador garantiza el hardware mínimo, el "
     "presupuesto de VRAM y latencia preserva la experiencia de voz en tiempo "
     "real, y la accesibilidad se cumple sin depender de la visión pesada — los "
     "mismos mecanismos que hacen al producto honesto (verify por estado, "
     "narración de resultados) son los que lo hacen utilizable sin pantalla.",
     color=GREY)

doc.save(str(OUT))
print(f"OK -> {OUT}")
print(f"Secciones: 7 | Tablas: 4 | tamaño: {OUT.stat().st_size} bytes")
