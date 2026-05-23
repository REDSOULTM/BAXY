"""Constructor del .pptx de DEFENSA DE TESIS — Gemma4 Agent.

Diseño coherente, oscuro técnico, pensado para presentar EN VIVO (poco texto,
una idea por slide, mucho visual). 12 slides según el spec del usuario.

Toda la data es REAL, verificada contra el código (modes.py, tool_schemas:
65 tools) y los reportes (bench/latency_sprint_report.md, llm_e2e_validation.md,
audit/PROJECT_CONSOLIDATION_FINAL.md, tradeoffs.md).

Salida: build/Gemma4_Agent_Tesis.pptx  (luego se copia a outputs/).
"""
from __future__ import annotations

import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

HERE = os.path.dirname(__file__)
ASSETS = os.path.join(HERE, "pptx_assets")

# ---- Paleta (idéntica a los diagramas) ------------------------------------
def C(hexstr): return RGBColor.from_string(hexstr)
BG      = C("0A0E14")
PANEL   = C("141A24")
PANEL2  = C("1C2430")
STROKE  = C("2A3340")
INK     = C("E6EDF3")
MUTE    = C("8B98A8")
ACCENT  = C("5BC8FF")
VIOLET  = C("9D7CFF")
GREEN   = C("3FB950")
ORANGE  = C("FF7A59")
YELLOW  = C("E3B341")
RED     = C("F85149")

EMU_W = Inches(13.333)
EMU_H = Inches(7.5)

prs = Presentation()
prs.slide_width = EMU_W
prs.slide_height = EMU_H
BLANK = prs.slide_layouts[6]

_n = [0]


def _slide():
    s = prs.slides.add_slide(BLANK)
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, EMU_W, EMU_H)
    r.fill.solid(); r.fill.fore_color.rgb = BG
    r.line.fill.background()
    r.shadow.inherit = False
    # mandar el fondo al fondo
    sp = r._element
    sp.getparent().remove(sp)
    s.shapes._spTree.insert(2, sp)
    return s


def _no_shadow(shape):
    shape.shadow.inherit = False


def box(s, x, y, w, h, *, fill=PANEL, line=STROKE, lw=1.0, round_=True):
    shp = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if round_ else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = Pt(lw)
    _no_shadow(shp)
    if round_:
        try:
            shp.adjustments[0] = 0.06
        except Exception:
            pass
    return shp


def text(s, x, y, w, h, runs, *, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         space_after=4):
    """runs: list of (txt, size, color, bold) or list of lines where each line
    is such a list."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    if runs and isinstance(runs[0], tuple):
        runs = [runs]
    for i, line in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        p.space_before = Pt(0)
        for (txt, size, color, bold) in line:
            r = p.add_run(); r.text = txt
            r.font.size = Pt(size); r.font.color.rgb = color
            r.font.bold = bold; r.font.name = "Segoe UI"
    return tb


def title_bar(s, kicker, ttl, *, accent=ACCENT):
    # barra de acento vertical
    bar = box(s, 0.55, 0.55, 0.10, 0.95, fill=accent, line=None, round_=False)
    text(s, 0.85, 0.50, 11.5, 0.45,
         [(kicker.upper(), 13, accent, True)], anchor=MSO_ANCHOR.MIDDLE)
    text(s, 0.83, 0.85, 11.8, 0.75,
         [(ttl, 30, INK, True)], anchor=MSO_ANCHOR.MIDDLE)


def footer(s):
    _n[0] += 1
    text(s, 0.85, 7.02, 7.0, 0.35,
         [("Gemma4 Agent", 9, MUTE, False)], anchor=MSO_ANCHOR.MIDDLE)
    text(s, 11.3, 7.02, 1.4, 0.35,
         [(f"{_n[0]:02d}", 10, MUTE, True)], align=PP_ALIGN.RIGHT,
         anchor=MSO_ANCHOR.MIDDLE)


def pic(s, name, x, y, w, h=None):
    p = os.path.join(ASSETS, name)
    if h is None:
        return s.shapes.add_picture(p, Inches(x), Inches(y), width=Inches(w))
    return s.shapes.add_picture(p, Inches(x), Inches(y), Inches(w), Inches(h))


def chip(s, x, y, w, h, label, *, color=ACCENT):
    b = box(s, x, y, w, h, fill=PANEL2, line=color, lw=1.5)
    text(s, x, y, w, h, [(label, 12, color, True)],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    return b


def table(s, x, y, w, rows, col_w, *, header_fill=PANEL2, head_color=ACCENT,
          row_h=0.42, head_h=0.5, fs=11, head_fs=11.5, zebra=True):
    """Tabla con diseño limpio (no la gris default). rows[0] = header."""
    cy = y
    for ri, row in enumerate(rows):
        is_head = ri == 0
        rh = head_h if is_head else row_h
        cx = x
        for ci, cell in enumerate(row):
            cwi = col_w[ci]
            fill = header_fill if is_head else (PANEL if (ri % 2 == 1 or not zebra) else PANEL2)
            cellbox = box(s, cx, cy, cwi, rh, fill=fill, line=None, round_=False)
            col = head_color if is_head else INK
            bold = is_head
            # primera columna de datos en mute si no header
            txt, *rest = (cell if isinstance(cell, tuple) else (cell,))
            ccol = rest[0] if rest else col
            text(s, cx + 0.08, cy, cwi - 0.12, rh,
                 [(txt, head_fs if is_head else fs, ccol if not is_head else head_color, bold)],
                 anchor=MSO_ANCHOR.MIDDLE,
                 align=PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER)
            cx += cwi
        cy += rh
    # línea bajo header
    return cy


def bullets(s, x, y, w, h, items, *, fs=15, gap=10, marker="—", mcolor=ACCENT):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap); p.space_before = Pt(0)
        m = p.add_run(); m.text = marker + "  "
        m.font.size = Pt(fs); m.font.color.rgb = mcolor; m.font.bold = True
        m.font.name = "Segoe UI"
        if isinstance(it, tuple):
            head, rest = it
            r = p.add_run(); r.text = head
            r.font.size = Pt(fs); r.font.color.rgb = INK; r.font.bold = True
            r.font.name = "Segoe UI"
            if rest:
                r2 = p.add_run(); r2.text = "  " + rest
                r2.font.size = Pt(fs - 1); r2.font.color.rgb = MUTE
                r2.font.name = "Segoe UI"
        else:
            r = p.add_run(); r.text = it
            r.font.size = Pt(fs); r.font.color.rgb = INK
            r.font.name = "Segoe UI"
    return tb


# ===========================================================================
# SLIDE 1 — Portada
# ===========================================================================
s = _slide()
# panel de acento sutil a la derecha
box(s, 8.4, 0, 4.93, 7.5, fill=PANEL, line=None, round_=False)
box(s, 8.4, 0, 0.06, 7.5, fill=ACCENT, line=None, round_=False)
text(s, 0.9, 1.6, 7.2, 0.5, [("DEFENSA DE TESIS", 15, ACCENT, True)])
text(s, 0.86, 2.15, 7.4, 1.6,
     [[("Gemma4 Agent", 50, INK, True)]])
text(s, 0.9, 3.5, 7.0, 1.4,
     [[("Una Alexa para tu PC —", 23, INK, True)],
      [("local, instalable, sin nube.", 23, GREEN, True)]],
     space_after=4)
text(s, 0.9, 5.4, 7.0, 1.2,
     [[("¿Es viable hoy un asistente de voz local que ejecute", 14, MUTE, False)],
      [("acciones reales en Windows con latencia usable?", 14, MUTE, False)]],
     space_after=3)
# chips lado derecho
chip(s, 8.95, 2.3, 3.7, 0.62, "100% local · sin nube", color=GREEN)
chip(s, 8.95, 3.15, 3.7, 0.62, "Gemma 4 · llama.cpp", color=ACCENT)
chip(s, 8.95, 4.0, 3.7, 0.62, "65 herramientas", color=VIOLET)
chip(s, 8.95, 4.85, 3.7, 0.62, "voz: hablás y hace", color=ORANGE)
footer(s)

# ===========================================================================
# SLIDE 2 — El problema
# ===========================================================================
s = _slide()
title_bar(s, "El problema", "Nadie le habla a su PC para que la maneje")
bullets(s, 0.9, 2.15, 7.1, 4.4, [
    ("Asistentes de voz:", "Alexa, Siri — fáciles, pero en la nube y no controlan tu PC."),
    ("Agentes potentes:", "Claude Code, Cowork — controlan la máquina, pero son para técnicos."),
    ("Todos cobran o espían:", "suscripción o tu voz viaja a un servidor ajeno."),
    ("El usuario común queda afuera.", ""),
], fs=16, gap=22, mcolor=ACCENT)
# caja-pregunta a la derecha
box(s, 8.4, 2.2, 4.3, 3.4, fill=PANEL, line=STROKE, lw=1.2)
text(s, 8.7, 2.5, 3.7, 2.9,
     [[("“Quiero que mi", 19, INK, True)],
      [("computadora me", 19, INK, True)],
      [("entienda y haga", 19, INK, True)],
      [("lo que le pido —", 19, INK, True)],
      [("sin pagar ni", 19, GREEN, True)],
      [("instalar líos.”", 19, GREEN, True)]], space_after=2)
footer(s)

# ===========================================================================
# SLIDE 3 — La idea (visual fuerte)
# ===========================================================================
s = _slide()
title_bar(s, "La idea", "Una Alexa para el PC — local e instalable", accent=GREEN)
# turn_flow 13.33x5.4 -> a 11.9 ancho da 4.82 alto; lo bajamos a 8.9 para entrar
pic(s, "turn_flow.png", (13.333 - 8.9) / 2, 2.5, 8.9)
text(s, 0.9, 6.15, 11.5, 0.6,
     [[("Hablás natural · el modelo decide · ejecuta en Windows · te confirma por voz. Todo en tu máquina.",
        15, INK, True)]], align=PP_ALIGN.CENTER)
footer(s)

# ===========================================================================
# SLIDE 4 — Posicionamiento honesto
# ===========================================================================
s = _slide()
title_bar(s, "Posicionamiento honesto", "El competidor no es Claude — es Alexa", accent=VIOLET)
# positioning.png es 13.33x6.2 (ratio 0.465). A 9.4" de ancho -> 4.37" alto.
pic(s, "positioning.png", 1.97, 1.75, 9.4)
text(s, 0.9, 6.35, 11.5, 0.5,
     [[("Honesto: en razonamiento profundo o visión, un modelo gigante en la nube todavía gana. "
        "Gemma4 gana en privacidad, costo y control directo del PC.", 12.5, MUTE, False)]],
     align=PP_ALIGN.CENTER)
footer(s)

# ===========================================================================
# SLIDE 5 — Cómo funciona (flujo de un turno)  -> ya está en turn_flow,
#           acá mostramos modos/decisión del agente
# ===========================================================================
s = _slide()
title_bar(s, "Cómo decide", "El agente elige cuánto pensar según lo que pedís")
table(s, 0.9, 2.15, 11.5, [
    ("Tipo de pedido", "Modo", "Piensa", "Tope tokens", "Para qué"),
    ("“hola”, “gracias”", "fast_action", ("OFF", GREEN), "128", ("charla rápida", MUTE)),
    ("“¿capital de Francia?”", "fast_info", ("OFF", GREEN), "320", ("responder, no divagar", MUTE)),
    ("“abre la calculadora”", "quick_action", ("ON", YELLOW), "512", ("decidir + 1 acción", MUTE)),
    ("“abre Chrome y pon música”", "deep_action", ("ON", YELLOW), "2048", ("varias acciones", MUTE)),
    ("“investiga X y dame fuentes”", "research", ("ON", YELLOW), "2048", ("buscar en la web", MUTE)),
], col_w=[3.5, 2.0, 1.3, 1.8, 2.9], row_h=0.55, head_h=0.55, fs=12.5, head_fs=12.5)
text(s, 0.9, 6.0, 11.5, 0.7,
     [[("Decisión clave de latencia: no pensar en preguntas simples. ", 14, INK, True),
       ("Eso bajó la mediana de 4.0 s a 1.9 s — y mejoró la calidad.", 14, GREEN, True)]],
     align=PP_ALIGN.CENTER)
footer(s)

# ===========================================================================
# SLIDE 6 — Pipeline de voz con latencias reales
# ===========================================================================
s = _slide()
title_bar(s, "Pipeline de voz", "De tu voz a la acción — todo medido", accent=VIOLET)
pic(s, "voice.png", (13.333 - 10.0) / 2, 2.05, 10.0)
text(s, 0.9, 6.4, 11.5, 0.5,
     [[("Wake 0.00 falsos/hora · STT en CPU (RTF 0.05) · LLM TTFT 22–73 ms · ~55 tok/s en E4B-Q6.",
        12.5, MUTE, False)]], align=PP_ALIGN.CENTER)
footer(s)

# ===========================================================================
# SLIDE 7 — Qué puede hacer hoy (65 tools)
# ===========================================================================
s = _slide()
title_bar(s, "Qué puede hacer hoy", "65 herramientas reales sobre Windows", accent=ORANGE)
# capabilities 13.33x5.7 (ratio .428) -> 12.0 ancho = 5.13 alto, entra bajo el título
pic(s, "capabilities.png", (13.333 - 12.0) / 2, 1.75, 12.0)
footer(s)

# ===========================================================================
# SLIDE 8 — ¿Es viable? (veredicto con evidencia)
# ===========================================================================
s = _slide()
title_bar(s, "¿Es viable?", "Sí — y está medido, no asumido", accent=GREEN)
pic(s, "viability.png", 0.5, 1.85, 7.6)
# panel de veredicto a la derecha
box(s, 8.35, 1.95, 4.4, 4.5, fill=PANEL, line=GREEN, lw=1.5)
text(s, 8.65, 2.2, 3.9, 0.5, [("LA EVIDENCIA", 13, GREEN, True)])
bullets(s, 8.65, 2.75, 3.85, 3.5, [
    ("Preguntas < 1.1 s", ""),
    ("Acciones < 5 s", ""),
    ("Todo el rango de GPU", ""),
    ("Calidad 0.989 (subió)", ""),
    ("27 bugs corregidos", ""),
], fs=14, gap=16, mcolor=GREEN)
footer(s)

# ===========================================================================
# SLIDE 9 — Qué NO puede hacer todavía (honesto)
# ===========================================================================
s = _slide()
title_bar(s, "Qué no puede todavía", "Los límites honestos (de tradeoffs.md)", accent=YELLOW)
bullets(s, 0.9, 2.05, 11.6, 4.6, [
    ("Hablar mientras piensa (streaming a voz):", "la infra existe, pero chocaría con los controles que evitan que el agente mienta. No se activó por seguridad."),
    ("Multi-acción en < 5 s:", "“abre Chrome y pon música” son varios pasos reales con verificación → ~10 s. Trabajo legítimo, no desperdicio."),
    ("Razonamiento profundo / visión compleja:", "un modelo local pequeño no iguala a uno gigante en la nube. Es el precio de ser 100% local y gratis."),
    ("Decisiones de producto abiertas:", "límite de cola de mensajes, arranque en frío sin medir. Documentadas, no ocultas."),
], fs=15, gap=20, mcolor=YELLOW)
footer(s)

# ===========================================================================
# SLIDE 10 — Qué podrá hacer (futuro)
# ===========================================================================
s = _slide()
title_bar(s, "Hacia dónde va", "El roadmap — marcado como futuro", accent=ACCENT)
# dos columnas: HOY vs FUTURO
box(s, 0.9, 2.1, 5.6, 4.2, fill=PANEL, line=GREEN, lw=1.4)
text(s, 1.2, 2.35, 5.0, 0.5, [("YA FUNCIONA", 14, GREEN, True)])
bullets(s, 1.2, 2.9, 5.1, 3.3, [
    "Voz local de punta a punta",
    "65 acciones reales en Windows",
    "Preguntas < 1.1 s",
    "6 perfiles de GPU (3–16 GB)",
], fs=13.5, gap=12, mcolor=GREEN, marker="✓")
box(s, 6.75, 2.1, 5.6, 4.2, fill=PANEL, line=YELLOW, lw=1.4)
text(s, 7.05, 2.35, 5.0, 0.5, [("FUTURO (planeado)", 14, YELLOW, True)])
bullets(s, 7.05, 2.9, 5.1, 3.3, [
    "Voz en streaming → ~1 s percibido",
    "Multi-acción en paralelo (< 5 s)",
    "Instalador de un clic para usuario final",
    "Más idiomas / acentos en el wake",
], fs=13.5, gap=12, mcolor=YELLOW, marker="→")
footer(s)

# ===========================================================================
# SLIDE 11 — DEMO (guion en vivo)
# ===========================================================================
s = _slide()
title_bar(s, "Demo en vivo", "Lo que voy a pedirle (con tiempos reales)", accent=ORANGE)
table(s, 0.9, 2.1, 11.5, [
    ("Le digo…", "Hace", "Tiempo esperado"),
    ("“hola”", "saluda por voz", ("~0.7 s", GREEN)),
    ("“¿cuál es la capital de Francia?”", "responde “París”", ("~1.1 s", GREEN)),
    ("“abre la calculadora”", "abre la app + confirma", ("~2.3 s", GREEN)),
    ("“minimiza la ventana”", "minimiza + confirma", ("~1.7 s", GREEN)),
    ("“abre Chrome y pon música”", "2 acciones encadenadas", ("~10 s", YELLOW)),
], col_w=[5.2, 3.8, 2.5], row_h=0.5, head_h=0.55, fs=13, head_fs=12.5)
text(s, 0.9, 5.75, 11.5, 0.9,
     [[("Respaldo si el micrófono falla: ", 13, INK, True),
       ("estos tiempos están medidos, no estimados. La demo en vivo la hago yo "
        "hablándole al agente.", 13, MUTE, False)]],
     align=PP_ALIGN.LEFT)
footer(s)

# ===========================================================================
# SLIDE 12 — Cierre
# ===========================================================================
s = _slide()
box(s, 8.4, 0, 4.93, 7.5, fill=PANEL, line=None, round_=False)
box(s, 8.4, 0, 0.06, 7.5, fill=GREEN, line=None, round_=False)
text(s, 0.9, 1.7, 7.2, 0.5, [("VEREDICTO", 15, GREEN, True)])
text(s, 0.86, 2.25, 7.4, 2.2,
     [[("La tesis es", 40, INK, True)],
      [("viable.", 40, GREEN, True)]], space_after=2)
text(s, 0.9, 4.2, 7.1, 2.2,
     [[("Un asistente de voz local, instalable, que ejecuta", 16, INK, False)],
      [("acciones reales en Windows con latencia usable —", 16, INK, False)],
      [("medido, no asumido.", 16, INK, True)]], space_after=4)
# tarjeta resumen derecha
text(s, 8.95, 2.2, 3.6, 0.5, [("EN UNA FRASE", 12, GREEN, True)])
bullets(s, 8.95, 2.8, 3.6, 3.8, [
    ("Local", "sin nube, privado"),
    ("Gratis", "sin suscripción"),
    ("Simple", "instalar y hablar"),
    ("Real", "65 acciones medidas"),
], fs=14, gap=16, mcolor=GREEN, marker="✓")
footer(s)

out = os.path.join(HERE, "Gemma4_Agent_Tesis.pptx")
prs.save(out)
print("OK ->", out, "·", len(prs.slides._sldIdLst), "slides")
