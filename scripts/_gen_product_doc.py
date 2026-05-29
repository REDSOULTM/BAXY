"""Genera el Word de producto (Riesgos+Mitigaciones + Comparativa competencia) para
Gemma 4 Agent, pensado en el PRODUCTO FINAL: app de instalar-y-usar, ≤4 GB VRAM/RAM,
para cualquier persona incluyendo no videntes y con movilidad reducida. Insumos:
visión de Carter (predecesor), ANALISIS_COMPETENCIA, números de VRAM medidos.
Honestidad (regla #3): se marca [MEDIDO] vs [ESTIMADO] vs [VISIÓN/OBJETIVO]."""
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Gemma4_Agent_Producto_Riesgos_y_Competencia.docx"

NAVY = RGBColor(0x1F, 0x38, 0x64)
GREY = RGBColor(0x55, 0x55, 0x55)
RED = RGBColor(0xA3, 0x1B, 0x1B)
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
        # shading
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
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
sub2.add_run("Asistente de voz local para Windows · privado · gratis · accesible · ≤4 GB VRAM\n"
             "Pensado para el PRODUCTO FINAL · 2026").italic = True
doc.add_paragraph()
note = doc.add_paragraph()
note.add_run("Convención de honestidad: ").bold = True
note.add_run("[MEDIDO] = verificado con números esta etapa · [ESTIMADO] = cálculo razonado "
             "sin medición exacta · [OBJETIVO] = meta del producto final, aún no garantizada.").italic = True

# ============================== 1. VISIÓN ==============================
h("1. Propósito y visión del producto final", 1)
para("Gemma 4 Agent es un asistente de voz que corre 100% en la PC del usuario (sin nube, "
     "sin cuentas, sin costo) y actúa sobre Windows por comandos en lenguaje natural: abrir "
     "apps, controlar el sistema, buscar y analizar archivos, navegar, leer/responder mensajes, "
     "programar recordatorios — verificando lo que hizo y reportándolo con honestidad.")
para("Es el sucesor de “Carter OS AI”, un proyecto anterior con la misma visión (un “Jarvis "
     "local para Windows: rápido, privado, universal, verificable”) que no llegó a producto. "
     "Gemma 4 Agent nace para cumplir esa visión corrigiendo las causas concretas del fracaso "
     "de Carter (ver §6), y agrega un eje que Carter nunca documentó: la accesibilidad.")
para("Tres promesas que definen el producto final:", bold=True)
bullet(" la app se instala y se usa; no requiere conocimiento técnico, edición de configs ni montar servidores.", "Instalar y usar —")
bullet(" funciona en una laptop modesta (≤4 GB de VRAM, con fallback a CPU), sin GPU de gama alta.", "Hardware accesible —")
bullet(" pensado desde el diseño para personas que no ven la pantalla y/o no pueden usar mouse/teclado (movilidad reducida, sin brazos). La voz no es un extra: es la vía principal.", "Accesible de verdad —")

# ============================== 2. PÚBLICO + ACCESIBILIDAD ==============================
h("2. Público objetivo y accesibilidad", 1)
para("El producto apunta a tres perfiles, con el mismo binario y sin modos “de segunda”:")
bullet(" usa la PC normalmente; quiere automatizar tareas por voz y mantener su privacidad.", "Usuario general —")
bullet(" no puede confiar en la pantalla; necesita que el asistente describa lo que ocurre y confirme resultados hablando, no mostrando.", "Persona no vidente —")
bullet(" no puede usar mouse/teclado de forma confiable; necesita ejecutar tareas completas solo con la voz, sin que el asistente le pida “hacé clic” o “mirá la pantalla”.", "Persona con movilidad reducida (sin brazos, etc.) —")
para("Implicación de diseño (no negociable): el asistente debe COMPLETAR la tarea él mismo y "
     "NARRAR el resultado. Nunca delegar “revisá la pantalla y elegí”. Esto ya está implementado "
     "como modos de accesibilidad (movilidad / no_vidente) con guardas que detectan y corrigen "
     "respuestas que delegan en el usuario. [MEDIDO esta etapa: el guard de delegación funciona; "
     "ver Riesgo R8 por un caso límite ya corregido].")

# ============================== 3. RECURSOS ==============================
h("3. Requisitos de recursos y consumo", 1)
para("El objetivo duro es caber en 4 GB de VRAM con el modelo, la visión y la voz activas, "
     "porque ese es el techo de una laptop típica con GPU de entrada. La voz (reconocimiento, "
     "síntesis) y los embeddings corren en CPU y cuestan 0 VRAM.")
table(
    ["Componente", "VRAM", "RAM", "Fuente / nota"],
    [
        ["LLM Gemma E2B-Q4 (perfil único 'vram4')", "~1.5 GB", "—", "[MEDIDO] quant table; reasoning menor que E4B, compensado con guardas"],
        ["mmproj visión F16 (screenshots)", "~1.0 GB", "—", "[MEDIDO] obligatorio para ver pantalla; gateado por presupuesto"],
        ["KV cache (contexto 16k)", "~0.4 GB", "—", "[MEDIDO] crece con el contexto; prompt acotado ~5–12k"],
        ["Escritorio Windows @1080p", "~0.5 GB", "—", "[MEDIDO] típico WDDM"],
        ["STT (Whisper int8 / Parakeet)", "0 GB", "~0.5–1 GB", "[ESTIMADO] corre en CPU int8"],
        ["TTS Piper + wake-word + embeddings MiniLM", "0 GB", "~0.2 GB", "[MEDIDO] Piper 50 MB, MiniLM 60 MB, wake ONNX ~50 MB"],
        ["App (UI, runtime Python)", "0 GB", "~0.3–0.5 GB", "[ESTIMADO]"],
    ],
    widths=[2.6, 0.9, 0.9, 2.4],
)
para("Pico de VRAM con todo activo ≈ 3.0–3.4 GB → entra en 4 GB con margen. [MEDIDO]", bold=True, color=GREEN)
para("Consumo de RAM del conjunto ≈ 2–3 GB (depende del motor STT y de las apps que el usuario "
     "tenga abiertas). [ESTIMADO — pendiente de medición formal en la versión final]. "
     "Sin GPU dedicada, el LLM puede correr en CPU con mayor latencia (modo degradado).", color=GREY)

# ============================== 4. COMPETENCIA ==============================
h("4. Análisis competitivo", 1)
para("Se analizaron 10 proyectos del espacio de agentes/asistentes. El hallazgo central: "
     "ninguno ocupa el nicho de Gemma 4 Agent. Todos son nube, o modelos grandes, o frameworks "
     "para desarrolladores. El único asistente de voz personal comparable (Mark-XXXIX) depende "
     "de una API de nube de pago.", italic=False)
table(
    ["Producto", "Local / Nube", "Costo", "VRAM mín.", "Voz", "Multi-idioma", "Accesibilidad", "Privacidad"],
    [
        ["Gemma 4 Agent", "100% Local", "Gratis/OSS", "≤4 GB (o CPU)", "Sí (eje central)", "Sí (embeddings)", "Sí (no vidente + movilidad)", "Total (local)"],
        ["Agent-S", "Nube", "API de pago", "N/A (GPT-4V)", "No", "Parcial", "No", "Datos a la nube"],
        ["OS-Copilot", "Nube", "API de pago", "N/A", "No", "Hardcoded chino", "No", "Datos a la nube"],
        ["Open Interpreter", "Híbrido", "Según modelo", "Alta si local", "No", "Parcial", "No", "Según backend"],
        ["OpenHands", "Nube/Docker", "API de pago", "N/A", "No", "Parcial", "No", "Datos a la nube"],
        ["Goose", "Local (Rust)", "Según provider", "Media-alta", "No", "Parcial", "No", "Según provider"],
        ["Mark-XXXIX", "Nube", "Gemini de pago", "N/A", "Sí (cloud)", "Sí", "No documentada", "Datos a la nube"],
        ["openclaw", "Servidor", "Infra propia", "N/A", "No (texto)", "Sí", "No", "Según despliegue"],
        ["AutoGen", "Framework", "N modelos grandes", "Muy alta", "No", "—", "No", "Según uso"],
        ["LangGraph / AutoGPT", "Framework", "Según modelo", "Alta", "No", "—", "No", "Según uso"],
    ],
    widths=[1.5, 1.0, 1.0, 0.95, 0.85, 1.0, 1.3, 1.0],
)
para("Lectura estratégica: no competimos por “ser GPT-4”. Ganamos por ser el único asistente "
     "que es a la vez local, gratis, de voz, multilingüe, privado y accesible, en hardware modesto. "
     "Las mejores IDEAS de los competidores (recuperación de errores, memoria de experiencia, "
     "ejecución de código, protocolo MCP) se adoptan DENTRO de esas restricciones, no rompiéndolas.", bold=True)

# ============================== 5. RIESGOS Y MITIGACIONES ==============================
doc.add_page_break()
h("5. Riesgos y mitigaciones", 1)
para("Riesgos ordenados por impacto en el producto final. La columna “Estado” indica si la "
     "mitigación ya está implementada, parcial, o es un objetivo.")
table(
    ["#", "Riesgo", "Por qué importa", "Mitigación", "Estado"],
    [
        ["R1", "El LLM de 4B no orquesta capacidades sofisticadas (ignora reglas, no elige la herramienta correcta).",
         "Es el cuello de botella medido: prefiere herramientas básicas y no usa las especializadas (p. ej. analizar datos, cargar 'skills'). Mató funciones de Carter.",
         "Capa de grounding determinista: el LLM da el objetivo, el sistema lo enruta por ESTADO (extensión de archivo, ventana abierta) y compone con macros verificadas; no se depende de que el 4B componga solo.",
         "Parcial [MEDIDO]"],
        ["R2", "“Falso éxito”: decir “listo” sin haberlo hecho (el peor defecto de Carter).",
         "Mentir destruye la confianza, sobre todo para un usuario que no ve la pantalla y no puede verificar.",
         "Verificación tri-estado por estado del SO (confirmado / no / desconocido), nunca por auto-juicio del LLM; guardas anti-promesa y anti-falsa-confirmación.",
         "Implementado [MEDIDO]"],
        ["R3", "GUI frágil en apps modernas (Electron/Chromium/Canvas).",
         "Discord, Spotify, navegadores rompen la automatización por accesibilidad; Carter perdía ahí.",
         "Cascada UIA → OCR → visión con verificación por estado; techos honestos documentados (si no se puede, se dice, no se finge).",
         "Implementado [MEDIDO]"],
        ["R4", "Accesibilidad: el asistente delega en el usuario (“revisá la pantalla”, “hacé clic”).",
         "Para no videntes / sin movilidad eso es inaceptable: la tarea queda sin completar.",
         "Modos de accesibilidad (movilidad / no_vidente) + guard que detecta delegación y re-prompta para que el agente ejecute el siguiente paso él mismo + narre el resultado.",
         "Implementado [MEDIDO]"],
        ["R5", "No caber en 4 GB / fuga de VRAM de la visión (llama.cpp #21690).",
         "Si se va de 4 GB, la app no arranca o crashea en la máquina objetivo.",
         "Perfil único optimizado a ≤4 GB; visión gateada por presupuesto (máx. llamadas/misión) + watchdog de VRAM; flash-attn off (evita crash CUDA).",
         "Implementado [MEDIDO]"],
        ["R6", "Latencia vs. robustez (antagónicos): agregar visión/razonamiento rompe la experiencia tipo Alexa.",
         "Más de 8 s por turno de voz es UX catastrófica.",
         "Presupuesto explícito 4–5 s; prefix-cache (−~1 s/acción medido), prompt 'lean', no inflar el contexto; visión solo cuando hace falta.",
         "Implementado [MEDIDO]"],
        ["R7", "Scope explosivo (Carter llegó a 57 herramientas y se diluyó).",
         "Más herramientas = peor elección del 4B y más superficie de fallo.",
         "Conjunto 'core' adaptativo por uso real (Pareto); no se agrega una herramienta sin medir que el 4B la use; MCP (catálogo externo) tratado con cautela por esto.",
         "Implementado [MEDIDO]"],
        ["R8", "Instalación compleja (drivers CUDA, modelos de GB, dependencias).",
         "Si no es “instalar y usar”, el público general y con discapacidad no lo adopta.",
         "El instalador debe garantizar precondiciones (modelos, binarios, deps) y degradar a CPU si no hay GPU; objetivo: cero pasos manuales.",
         "Objetivo [parcial hoy]"],
        ["R9", "Seguridad: acciones irreversibles (borrar, enviar, comprar) o LLM inducido a dañar.",
         "Un asistente con control del SO puede causar daño real.",
         "Confirmación obligatoria de acciones irreversibles (no auto-envía correos/mensajes; abre redactor), guard de compras, sandbox de filesystem, sin eval/exec de código del LLM.",
         "Implementado [MEDIDO]"],
        ["R10", "Privacidad: voz, pantalla y archivos son datos sensibles.",
         "Es el diferenciador frente a la competencia (toda en la nube).",
         "100% local; nada sale del equipo sin permiso explícito; sin cuentas ni telemetría obligatoria.",
         "Implementado [por diseño]"],
        ["R11", "Reconocimiento de voz/acentos imperfecto (multi-usuario, multi-idioma).",
         "Si no entiende a todos por igual, excluye usuarios — y a un no vidente le cuesta corregir.",
         "STT con corrector fonético + evaluación contra voces diversas (held-out), no sobre la voz del desarrollador; gate de recall por idioma.",
         "Parcial [MEDIDO]"],
        ["R12", "Dependencia de un LLM no determinista: el mismo pedido se enruta distinto.",
         "Hace difícil garantizar calidad y reproducir fallos.",
         "Validación EN VIVO obligatoria con variantes de fraseo antes de dar algo por hecho; guardas estructurales que acotan la forma (anti-loop, honestidad); suite de tests amplia.",
         "Implementado [MEDIDO]"],
    ],
    widths=[0.35, 1.7, 2.0, 2.4, 0.85],
)

# ============================== 6. LECCIONES DE CARTER ==============================
h("6. Lecciones del predecesor (Carter) ya incorporadas", 1)
para("Carter falló por causas concretas y documentadas en su propio post-mortem. Gemma 4 Agent "
     "las trata como riesgos de primera clase (mapa directo a §5):")
table(
    ["Causa de fracaso de Carter", "Corrección en Gemma 4 Agent"],
    [
        ["Decía “hecho” sin verificar (falso éxito)", "R2 — verificación por estado del SO, tri-estado honesto"],
        ["Hardcodes por app (if Steam / if Discord)", "R1/R3 — resolución por estado e intención, no listas por app"],
        ["Multi-paso débil (olvidaba el resto)", "R1 — splitter + macros deterministas + checkpoint de misión"],
        ["Scope explosivo (57 herramientas)", "R7 — core Pareto, no agregar sin medir uso"],
        ["Voz y visión nunca integradas (solo investigadas)", "Voz es el eje central y está en runtime; visión gateada y medida"],
        ["Evaluación sesgada (matriz propia)", "R12 — validación en vivo + tests; honestidad sobre lo no verificado"],
        ["Accesibilidad invisible (no documentada)", "§2/R4 — accesibilidad es requisito de diseño, con modos y guardas"],
        ["Latencia vs. robustez sin resolver", "R6 — presupuesto explícito + prefix-cache + prompt lean"],
    ],
    widths=[3.3, 3.3],
)

# ============================== 7. CONCLUSIÓN ==============================
h("7. Conclusión", 1)
para("Gemma 4 Agent ocupa un nicho que hoy nadie cubre: un asistente de voz local, privado, "
     "gratuito, multilingüe y accesible, en hardware modesto. La competencia no es un rival "
     "directo; es una fuente de buenas ideas a adoptar dentro de las restricciones.")
para("El riesgo dominante no es la falta de capacidades —el repositorio ya tiene más de las que "
     "el análisis de competencia asumía— sino la capacidad del modelo de 4B para ORQUESTARLAS, "
     "y la disciplina de no crecer en scope ni romper la latencia. Las mitigaciones clave (grounding "
     "determinista, verificación honesta, accesibilidad por diseño, presupuesto de recursos) ya "
     "están implementadas o en curso; el trabajo restante es de conexión y pulido, no de reinvención.", bold=True)
para("Los próximos pasos de mayor valor son: (1) cerrar la conexión de capacidades al 4B "
     "(que el modelo USE lo que ya existe), (2) el instalador “cero pasos” (R8), y (3) medir "
     "formalmente el consumo de RAM y la accesibilidad con usuarios reales.", color=GREY)

doc.save(str(OUT))
print(f"OK -> {OUT}")
print(f"Secciones: 7 | Tablas: 4 | tamaño: {OUT.stat().st_size} bytes")
