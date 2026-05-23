# -*- coding: utf-8 -*-
"""Genera el documento Word de tesis de Gemma4 Agent:
  1. Diagrama + estudio de arquitectura técnica
  2. Estudio de mercado (por qué nuestra propuesta es mejor)
  3. Evaluación técnico-legal (privacidad, licencias OSS, ToS de terceros)

Datos REALES verificados contra el repo:
  - requirements.txt (versiones y licencias de cada componente)
  - docs/ARCHITECTURE.md (mapa de capas, invariantes, 27 fixes)
  - bench/latency_sprint_report.md (latencias medidas)
  - tool_schemas.COMPOUND_TOOL_SCHEMAS (65 tools)
  - memoria del proyecto (perfiles VRAM, modelos/quants)

Salida: build/Gemma4_Agent_Arquitectura_Mercado_Legal.docx -> copiar a outputs/
"""
from __future__ import annotations
import os
from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = os.path.dirname(__file__)
ASSETS = os.path.join(HERE, "pptx_assets")

# Paleta (coherente con la presentación)
INK   = RGBColor(0x1A, 0x20, 0x28)
CYAN  = RGBColor(0x0E, 0x6B, 0xA8)   # acento (oscurecido para leer en blanco)
GREEN = RGBColor(0x1E, 0x7E, 0x34)
ORANGE= RGBColor(0xB5, 0x4A, 0x1F)
VIOLET= RGBColor(0x5B, 0x3E, 0xA8)
MUTE  = RGBColor(0x60, 0x6A, 0x76)
RED   = RGBColor(0xB0, 0x2A, 0x1F)

doc = Document()

# ---- estilos base ----
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11)
normal.font.color.rgb = INK
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.15

for lvl, sz, col in [("Heading 1", 18, CYAN), ("Heading 2", 14, INK), ("Heading 3", 12, MUTE)]:
    st = doc.styles[lvl]
    st.font.name = "Calibri"
    st.font.size = Pt(sz)
    st.font.color.rgb = col
    st.font.bold = True


def _shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:fill"), hexcolor)
    tcPr.append(sh)


def p(text="", *, size=11, bold=False, italic=False, color=INK, align=None, after=6, before=0):
    par = doc.add_paragraph()
    if align is not None:
        par.alignment = align
    par.paragraph_format.space_after = Pt(after)
    par.paragraph_format.space_before = Pt(before)
    r = par.add_run(text)
    r.font.size = Pt(size); r.bold = bold; r.italic = italic; r.font.color.rgb = color
    return par


def runs(par_text_runs, *, after=6):
    """par_text_runs: list of (text, dict-of-style)."""
    par = doc.add_paragraph()
    par.paragraph_format.space_after = Pt(after)
    for txt, st in par_text_runs:
        r = par.add_run(txt)
        r.font.size = Pt(st.get("size", 11))
        r.bold = st.get("bold", False)
        r.italic = st.get("italic", False)
        r.font.color.rgb = st.get("color", INK)
    return par


def bullet(text, *, bold_lead=None, color=INK, size=11):
    par = doc.add_paragraph(style="List Bullet")
    par.paragraph_format.space_after = Pt(4)
    if bold_lead:
        r = par.add_run(bold_lead + " ")
        r.bold = True; r.font.size = Pt(size); r.font.color.rgb = color
    r2 = par.add_run(text)
    r2.font.size = Pt(size); r2.font.color.rgb = color
    return par


def table(headers, rows, *, widths=None, head_fill="0E6BA8", zebra="EEF3F8"):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        _shade(hdr[i], head_fill)
        para = hdr[i].paragraphs[0]
        para.paragraph_format.space_after = Pt(2); para.paragraph_format.space_before = Pt(2)
        run = para.add_run(h)
        run.bold = True; run.font.size = Pt(10); run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for ci, val in enumerate(row):
            if zebra and ri % 2 == 1:
                _shade(cells[ci], zebra)
            para = cells[ci].paragraphs[0]
            para.paragraph_format.space_after = Pt(2); para.paragraph_format.space_before = Pt(2)
            # val puede ser (texto, color)
            if isinstance(val, tuple):
                txt, col = val
            else:
                txt, col = val, INK
            run = para.add_run(str(txt))
            run.font.size = Pt(9.5); run.font.color.rgb = col
            if ci == 0:
                run.bold = True
    if widths:
        for row in t.rows:
            for ci, wdt in enumerate(widths):
                row.cells[ci].width = Cm(wdt)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t


def hr():
    par = doc.add_paragraph()
    pPr = par._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1"); bottom.set(qn("w:color"), "C6CFD8")
    pbdr.append(bottom); pPr.append(pbdr)


def callout(title, body, *, color=CYAN, fill="EEF3F8"):
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    c = t.rows[0].cells[0]
    _shade(c, fill)
    pr = c.paragraphs[0]; pr.paragraph_format.space_after = Pt(2)
    r = pr.add_run(title); r.bold = True; r.font.size = Pt(10.5); r.font.color.rgb = color
    pr2 = c.add_paragraph(); pr2.paragraph_format.space_after = Pt(2)
    r2 = pr2.add_run(body); r2.font.size = Pt(10); r2.font.color.rgb = INK
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t


# =========================================================================
# PORTADA
# =========================================================================
for _ in range(3):
    doc.add_paragraph()
p("GEMMA4 AGENT", size=30, bold=True, color=CYAN, align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
p("Asistente de voz local para Windows", size=16, color=INK, align=WD_ALIGN_PARAGRAPH.CENTER, after=24)
p("Arquitectura técnica · Estudio de mercado · Evaluación técnico-legal",
  size=13, bold=True, color=MUTE, align=WD_ALIGN_PARAGRAPH.CENTER, after=8)
p("Documento de respaldo de tesis", size=11, italic=True, color=MUTE,
  align=WD_ALIGN_PARAGRAPH.CENTER, after=40)
p("Versión 1.0 · 22 de mayo de 2026", size=10, color=MUTE, align=WD_ALIGN_PARAGRAPH.CENTER)
p("Documento generado a partir de datos verificados del repositorio del proyecto.",
  size=9, italic=True, color=MUTE, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_page_break()

# =========================================================================
# RESUMEN EJECUTIVO
# =========================================================================
doc.add_heading("Resumen ejecutivo", level=1)
p("Gemma4 Agent es un asistente de voz que se ejecuta en su totalidad en la "
  "computadora del usuario (Windows), sin enviar voz ni datos a la nube y sin "
  "requerir suscripción a ningún servicio de IA. El usuario le habla en lenguaje "
  "natural —«abre Spotify y pon música», «sube el volumen», «minimiza la ventana»— "
  "y el sistema ejecuta acciones reales sobre el equipo mediante un conjunto de "
  "65 herramientas, confirmando el resultado por voz.")
p("La tesis que este documento respalda es concreta y medible: ", after=2, bold=False)
runs([("«¿Es viable hoy un asistente de voz local, instalable, que ejecute "
       "acciones reales en Windows con latencia usable?»", {"italic": True, "bold": True})])
p("La respuesta, sustentada en mediciones reales del proyecto, es afirmativa, "
  "con límites honestos que se detallan en este documento.")

table(
    ["Dimensión", "Resultado verificado"],
    [
        ("Latencia (preguntas)", "< 1.1 s en los tres modelos del lineup"),
        ("Latencia (acciones)", "≈ 2–5 s con confirmación verificada"),
        ("Privacidad", ("100 % local — los datos no salen del equipo", GREEN)),
        ("Costo de uso", ("Sin suscripción ni costo por token", GREEN)),
        ("Capacidades", "65 herramientas reales sobre Windows"),
        ("Rango de hardware", "Perfiles vram3 a vram16 (GPU 3–16 GB)"),
        ("Robustez", "27 errores corregidos en auditoría; suite verde"),
    ],
    widths=[5.5, 11.0],
)
doc.add_page_break()

# =========================================================================
# 1. ARQUITECTURA
# =========================================================================
doc.add_heading("1. Arquitectura técnica", level=1)
p("Esta sección describe la arquitectura del sistema tal como fue verificada por "
  "la auditoría del proyecto leyendo el código y midiendo en ejecución —no es un "
  "diseño aspiracional. La organización en capas obedece a un orden de prioridad "
  "explícito ante conflictos de diseño:")
bullet("invariantes preservados, hot-path limpio, dispatch como contenedor de fallos.",
       bold_lead="1) Arquitectura:")
bullet("nunca caer el turno, perder una respuesta, corromper la persistencia ni degradar en silencio.",
       bold_lead="2) Fiabilidad / calidad:")
bullet("hot-path y always-on rápidos; toda E/S crítica con timeout; lo costoso fuera del camino.",
       bold_lead="3) Latencia:")

doc.add_heading("1.1 Mapa de capas", level=2)
p("El diagrama siguiente muestra las capas del sistema y cómo se relacionan: las "
  "superficies de entrada, el procesamiento always-on de audio, el hot-path de un "
  "turno, la persistencia, los diagnósticos y los daemons de ciclo de vida.")
arch_png = os.path.join(ASSETS, "architecture_layers.png")
if os.path.exists(arch_png):
    doc.add_picture(arch_png, width=Inches(6.3))
    last = doc.paragraphs[-1]; last.alignment = WD_ALIGN_PARAGRAPH.CENTER
p("Figura 1. Mapa de capas de Gemma4 Agent (fiel a docs/ARCHITECTURE.md).",
  size=9, italic=True, color=MUTE, align=WD_ALIGN_PARAGRAPH.CENTER)

doc.add_heading("1.2 Flujo de un turno de voz", level=2)
p("Un turno recorre la cadena de voz y el hot-path del modelo. Cada flecha que "
  "cruza a un proceso, disco o modelo tiene su contención (timeout, try/except o "
  "recuperación), lo que mantiene los tres ejes de prioridad en el camino feliz:")
flow_png = os.path.join(ASSETS, "turn_flow.png")
if os.path.exists(flow_png):
    doc.add_picture(flow_png, width=Inches(6.0))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
p("Figura 2. Cadena voz → wake/VAD → STT → LLM local → acción → confirmación por voz.",
  size=9, italic=True, color=MUTE, align=WD_ALIGN_PARAGRAPH.CENTER)

doc.add_heading("1.3 Componentes y su rol", level=2)
table(
    ["Capa", "Componente", "Función", "Tecnología"],
    [
        ("Audio", "audio_io / VAD", "Captura y detección de voz", "PortAudio · Silero VAD"),
        ("Audio", "wake-word", "Palabra de activación («hey gemma»)", "LiveKit ONNX · 8 Hz"),
        ("STT", "transcripción", "Voz → texto, en CPU", "faster-whisper small int8"),
        ("LLM", "modelo local", "Razonamiento y elección de herramienta", "Gemma 4 · llama.cpp"),
        ("Router", "intent + semántico", "Selecciona el subconjunto de tools", "embeddings cacheados"),
        ("Dispatch", "ejecución de tools", "Corre la acción con verificación", "try/except + timeout por tool"),
        ("TTS", "síntesis de voz", "Texto → voz de respuesta", "Piper"),
        ("Persistencia", "state / experience", "Memoria y sesión, escritura atómica", "JSON atómico · SQLite"),
    ],
    widths=[2.4, 3.2, 5.2, 4.2],
)

doc.add_heading("1.4 Perfiles de hardware (escalado por VRAM)", level=2)
p("El sistema se adapta al hardware mediante perfiles que seleccionan el modelo y "
  "la cuantización adecuados a la VRAM disponible. Esto permite que funcione tanto "
  "en una GPU modesta como en una de gama alta sin cambiar el código.")
table(
    ["Perfil", "Modelo", "Cuantización", "Uso objetivo"],
    [
        ("vram3", "Gemma 4 E2B", "Q4_K_M", "GPU pequeña (~3 GB)"),
        ("vram4 / 6 / 8", "Gemma 4 E4B", "Q4_K_M", "GPU media (4–8 GB)"),
        ("vram12 / 16", "Gemma 4 E4B", "Q6_K", "GPU alta (12–16 GB)"),
    ],
    widths=[3.0, 3.5, 3.5, 5.0],
)

doc.add_heading("1.5 Invariantes de fiabilidad", level=2)
p("La auditoría confirmó un patrón nueve veces: los 27 errores reales vivieron en "
  "los bordes (persistencia, recuperación, daemons, teardown), nunca en el camino "
  "feliz. El hot-path se diseñó cuidando los tres ejes; los bordes recibieron el "
  "mismo cuidado al cerrarlos. Invariantes clave:")
bullet("cada herramienta corre en try/except y con timeout; una que falle se vuelve "
       "un error contenido, nunca aborta el turno.", bold_lead="Radio de explosión contenido:")
bullet("el callback de audio nunca bloquea; el wake se ejecuta decimado (~8 Hz) para "
       "−74 % de CPU en reposo sin perder recall.", bold_lead="Always-on no bloqueante:")
bullet("escritura atómica de estado; una base de datos corrupta se pone en cuarentena "
       "y se recrea, el turno sobrevive.", bold_lead="Persistencia recuperable:")
bullet("el servidor del modelo se detiene en atexit (sin huérfanos que retengan VRAM); "
       "nunca toca un servidor externo del usuario.", bold_lead="Ciclo de vida limpio:")
doc.add_page_break()

# =========================================================================
# 2. ESTUDIO DE MERCADO
# =========================================================================
doc.add_heading("2. Estudio de mercado", level=1)
p("El error más común al posicionar este proyecto es compararlo con agentes de IA "
  "para programadores. No compite con ellos: compite —y gana— en una categoría "
  "distinta, la del asistente de voz para el usuario común.")

doc.add_heading("2.1 Segmentación del mercado", level=2)
p("Existen dos familias de productos que el usuario podría considerar, y Gemma4 "
  "ocupa el espacio vacío entre ambas:")
bullet("Alexa, Siri, Cortana, Google Assistant. Fáciles de usar pero limitados: "
       "viven en la nube, dependen de servidores del fabricante y no controlan de "
       "verdad la computadora del usuario.", bold_lead="Asistentes de voz de consumo:")
bullet("Claude Code, Cowork, Open Interpreter. Potentes y controlan la máquina, "
       "pero están dirigidos a personas técnicas, requieren conocimientos de "
       "programación y una suscripción a un modelo en la nube.",
       bold_lead="Agentes de IA para desarrolladores:")
p("Gemma4 Agent combina la facilidad de los primeros con el control real de los "
  "segundos, ejecutándose 100 % local y sin suscripción. Su público objetivo es el "
  "usuario que dispone de un buen equipo (GPU dedicada) y quiere controlar su PC por "
  "voz sin pagar mensualidades ni enviar sus datos a terceros.")

doc.add_heading("2.2 Comparación competitiva", level=2)
table(
    ["Criterio", "Alexa / Siri", "Claude Code / Cowork", "Gemma4 Agent"],
    [
        ("Facilidad para usuario común", ("Alta", GREEN), ("Baja", RED), ("Alta", GREEN)),
        ("Ejecución 100 % local", ("No", RED), ("No", RED), ("Sí", GREEN)),
        ("Controla el PC de verdad", ("No", RED), ("Sí", GREEN), ("Sí", GREEN)),
        ("Sin suscripción / sin costo por uso", ("No", RED), ("No", RED), ("Sí", GREEN)),
        ("Privacidad (datos no salen del equipo)", ("No", RED), ("No", RED), ("Sí", GREEN)),
        ("Instalable por el usuario final", ("Sí", GREEN), ("Parcial", ORANGE), ("Sí", GREEN)),
        ("Razonamiento profundo / visión avanzada", ("Limitado", ORANGE), ("Alto", GREEN), ("Medio", ORANGE)),
        ("Funciona sin conexión a internet", ("No", RED), ("No", RED), ("Sí*", GREEN)),
    ],
    widths=[5.0, 3.6, 4.0, 3.6],
)
p("* Las acciones locales (apps, ventanas, volumen, archivos) no requieren internet. "
  "Solo las herramientas de búsqueda web lo necesitan, por naturaleza.",
  size=9, italic=True, color=MUTE)

doc.add_heading("2.3 Ventajas diferenciales", level=2)
bullet("la voz del usuario y sus datos nunca salen del equipo. Es el "
       "diferencial más fuerte frente a todo asistente de nube.",
       bold_lead="Privacidad por diseño:", color=INK)
bullet("sin suscripción mensual ni cobro por token. El único requisito es el "
       "hardware, que el usuario ya posee.", bold_lead="Costo cero de operación:")
bullet("se instala y se usa, sin necesidad de saber programar ni de "
       "configurar claves de API.", bold_lead="Instalable y simple:")
bullet("software libre y gratuito en su stack base; sin dependencia de un "
       "proveedor que pueda subir precios o discontinuar el servicio.",
       bold_lead="Sin lock-in:")

doc.add_heading("2.4 Limitaciones honestas (análisis de debilidades)", level=2)
p("Un estudio de mercado creíble reconoce dónde la propuesta no gana. Estas son las "
  "limitaciones reales del enfoque local:")
bullet("un modelo local pequeño no iguala el razonamiento ni la "
       "visión de un modelo gigante en la nube. Es el precio de la privacidad y el "
       "costo cero.", bold_lead="Capacidad del modelo:")
bullet("requiere una GPU dedicada razonable. No apunta al usuario "
       "sin hardware, sino al que ya tiene un buen equipo.", bold_lead="Requisito de hardware:")
bullet("encadenar varias acciones con verificación entre cada "
       "una toma ~10 s; es trabajo legítimo, pero más lento que un comando simple.",
       bold_lead="Latencia en multi-acción:")
doc.add_page_break()

# =========================================================================
# 3. EVALUACIÓN LEGAL
# =========================================================================
doc.add_heading("3. Evaluación técnico-legal", level=1)
callout(
    "Aviso importante",
    "Este análisis describe las implicancias legales del diseño técnico del "
    "proyecto y las licencias de sus componentes. NO constituye asesoría jurídica "
    "ni un dictamen legal. Para uso comercial o distribución pública se recomienda "
    "la revisión de un profesional del derecho.",
    color=RED, fill="FBEAE8",
)

doc.add_heading("3.1 Privacidad y protección de datos", level=2)
p("La característica de ejecución 100 % local tiene una consecuencia legal directa "
  "y favorable: al no transmitirse datos personales (voz, transcripciones, "
  "contenido de pantalla) a servidores de terceros, el sistema reduce drásticamente "
  "su superficie de cumplimiento en materia de protección de datos.")
bullet("el tratamiento de datos personales ocurre exclusivamente en el "
       "equipo del usuario, bajo su control. No hay transferencia a un responsable "
       "externo ni a otra jurisdicción.", bold_lead="Tratamiento local:")
bullet("frente al RGPD europeo (referencia internacional más estricta) "
       "y a las leyes de datos de Latinoamérica (p. ej., principios de finalidad, "
       "consentimiento y seguridad), el procesamiento local en el dispositivo del "
       "propio titular minimiza el rol del proyecto como «responsable del "
       "tratamiento».", bold_lead="Marco de referencia:")
bullet("captura de pantalla, micrófono y control de "
       "aplicaciones. Aunque local, el sistema debe informar al usuario de estas "
       "capacidades y operar bajo su consentimiento explícito.",
       bold_lead="Datos sensibles que el sistema toca:")

doc.add_heading("3.2 Licencias de los componentes (stack OSS)", level=2)
p("El stack base es software libre. La tabla siguiente lista los componentes "
  "principales con su licencia. Dos de ellos requieren atención especial y se "
  "analizan debajo.")
table(
    ["Componente", "Versión", "Licencia", "Implicancia"],
    [
        ("Gemma 4 (modelo)", "—", ("Gemma Terms of Use", ORANGE), "Términos propios de Google (ver 3.3)"),
        ("llama.cpp (inferencia)", "b9090", ("MIT", GREEN), "Permisiva — uso libre"),
        ("faster-whisper (STT)", "1.2.1", ("MIT", GREEN), "Permisiva"),
        ("Modelo Whisper (OpenAI)", "small", ("MIT", GREEN), "Permisiva"),
        ("silero-vad (VAD)", "6.2.1", ("MIT", GREEN), "Permisiva"),
        ("piper-tts (TTS)", "1.4.2", ("MIT", GREEN), "Permisiva"),
        ("openwakeword (wake)", "≥0.6", ("Apache 2.0", GREEN), "Permisiva con patente"),
        ("sentence-transformers", "5.3.0", ("Apache 2.0", GREEN), "Permisiva"),
        ("playwright (navegador)", "1.55.0", ("Apache 2.0", GREEN), "Permisiva"),
        ("FastAPI / uvicorn", "—", ("MIT / BSD", GREEN), "Permisiva"),
        ("PyQt6 (UI nativa)", "6.11.0", ("GPL v3 / comercial", RED), "Copyleft — ver 3.4"),
    ],
    widths=[4.6, 2.2, 3.6, 5.0],
)

doc.add_heading("3.3 Gemma — términos de uso del modelo", level=2)
p("Gemma 4 se distribuye bajo los «Gemma Terms of Use» de Google, que no son una "
  "licencia OSI tradicional. Puntos relevantes a considerar:")
bullet("permiten el uso, la reproducción y la modificación, incluso "
       "comercial, del modelo.", bold_lead="Uso amplio:")
bullet("Google publica una política de uso prohibido (Gemma "
       "Prohibited Use Policy) que el proyecto debe respetar y trasladar a sus "
       "usuarios.", bold_lead="Restricciones de uso:")
bullet("la distribución del modelo (o de derivados) debe "
       "acompañarse de los términos y avisos correspondientes.",
       bold_lead="Atribución y avisos:")
callout(
    "Recomendación",
    "Incluir los Gemma Terms of Use y la Prohibited Use Policy junto con el "
    "producto, y verificar la versión vigente de dichos términos antes de cualquier "
    "distribución pública, dado que Google puede actualizarlos.",
    color=CYAN,
)

doc.add_heading("3.4 PyQt6 — copyleft GPL", level=2)
p("PyQt6 se ofrece bajo licencia dual: GPL v3 o licencia comercial de Riverbank "
  "Computing. Si el proyecto se distribuye usando PyQt6 bajo GPL, la GPL v3 exige "
  "que el código fuente del producto se publique bajo términos compatibles "
  "(copyleft). Esto es relevante para una eventual comercialización con código cerrado.")
bullet("publicar el proyecto como software libre "
       "(compatible con GPL), o usar la UI web alternativa basada en pywebview "
       "(que evita la dependencia de PyQt), o adquirir la licencia comercial de "
       "PyQt.", bold_lead="Opciones:")
p("Nota técnica: el proyecto ya cuenta con una interfaz web (pywebview/React) además "
  "de la UI nativa PyQt, lo que ofrece una vía para evitar el copyleft de Qt si se "
  "desea distribución con código cerrado.", size=10, italic=True, color=MUTE)

doc.add_heading("3.5 Control de aplicaciones de terceros", level=2)
p("El agente puede controlar aplicaciones de terceros (p. ej., reproducir música en "
  "Spotify, abrir contenido en Netflix, navegar la web). Esto interactúa con los "
  "Términos de Servicio (ToS) de dichas plataformas:")
bullet("automatizar una app instalada por el usuario, en su propio "
       "equipo y para su uso personal, es generalmente equivalente a que el usuario "
       "la opere manualmente.", bold_lead="Uso personal:")
bullet("algunos ToS prohíben el acceso automatizado o el "
       "scraping. El proyecto debe evitar eludir DRM, no redistribuir contenido y no "
       "infringir medidas técnicas de protección.", bold_lead="Límites:")
bullet("el control se hace mediante la interfaz "
       "de usuario (teclas, ventanas) y no accede a APIs privadas ni almacena "
       "credenciales de terceros.", bold_lead="Postura recomendada:")

doc.add_heading("3.6 Síntesis legal", level=2)
table(
    ["Aspecto", "Estado", "Acción recomendada"],
    [
        ("Privacidad / datos", ("Favorable", GREEN), "Documentar el procesamiento local y pedir consentimiento de mic/pantalla"),
        ("Licencias OSS base", ("Permisivas", GREEN), "Mantener avisos de licencia (MIT/Apache/BSD)"),
        ("Modelo Gemma", ("Condicionado", ORANGE), "Incluir y respetar Gemma Terms + Prohibited Use Policy"),
        ("PyQt6 (UI)", ("Atención", RED), "Usar UI web, liberar bajo GPL o licenciar comercialmente"),
        ("ToS de terceros", ("Atención", ORANGE), "Uso personal vía UI; no eludir DRM ni APIs privadas"),
    ],
    widths=[4.0, 2.6, 8.4],
)
doc.add_page_break()

# =========================================================================
# CIERRE + FUENTES
# =========================================================================
doc.add_heading("Conclusión", level=1)
p("Gemma4 Agent ocupa un espacio de mercado real y no atendido: el asistente de voz "
  "que controla la computadora del usuario, de forma local, privada y sin "
  "suscripción. Su arquitectura está diseñada y auditada para la fiabilidad, con "
  "latencias medidas dentro del presupuesto de una experiencia de voz usable. Desde "
  "lo legal, su naturaleza local es una ventaja de cumplimiento en privacidad; los "
  "puntos a gestionar son los términos del modelo Gemma, la licencia copyleft de la "
  "UI nativa y el respeto a los términos de servicio de las aplicaciones que "
  "controla —todos manejables con las acciones recomendadas en este documento.")

doc.add_heading("Fuentes y trazabilidad", level=2)
p("Los datos de este documento provienen de artefactos verificables del repositorio "
  "del proyecto:", after=4)
for src in [
    "docs/ARCHITECTURE.md — mapa de capas, invariantes y tabla de 27 correcciones.",
    "bench/latency_sprint_report.md — latencias medidas por tipo de turno y perfil.",
    "bench/llm_e2e_validation.md — TTFT, velocidad de decodificación y recovery.",
    "requirements.txt — versiones exactas de los componentes y sus licencias.",
    "tool_schemas.COMPOUND_TOOL_SCHEMAS — inventario de 65 herramientas.",
    "Licencias oficiales: MIT (Whisper, llama.cpp, Piper, Silero), Apache 2.0 "
    "(openWakeWord, sentence-transformers, Playwright), Gemma Terms of Use (Google), "
    "GPL v3 / comercial (PyQt6 — Riverbank).",
]:
    bullet(src, size=10, color=MUTE)

out = os.path.join(HERE, "Gemma4_Agent_Arquitectura_Mercado_Legal.docx")
doc.save(out)
print("OK ->", out)
