# -*- coding: utf-8 -*-
"""Construye la presentación de arquitectura de Gemma4 Agent (.pptx).
Datos REALES verificados contra el repo. Estilo técnico oscuro, en español."""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

HERE = os.path.dirname(__file__)
ASSETS = os.path.join(HERE, "pptx_assets")

# Paleta (coherente con los diagramas)
BG = RGBColor(0x0A, 0x0E, 0x14)
INK = RGBColor(0xE6, 0xED, 0xF3)
MUT = RGBColor(0x8B, 0x97, 0xA7)
ACCENT = RGBColor(0x5B, 0xC8, 0xFF)
HOT = RGBColor(0xFF, 0x7A, 0x59)
AUDIO = RGBColor(0x7C, 0x5C, 0xFF)
PERSIST = RGBColor(0x3F, 0xB9, 0x50)
DIAG = RGBColor(0xD2, 0x99, 0x22)
CARD = RGBColor(0x14, 0x1A, 0x23)
EDGE = RGBColor(0x2A, 0x34, 0x41)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]


def slide():
    s = prs.slides.add_slide(BLANK)
    bg = s.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = BG
    return s


def box(s, x, y, w, h, fill=None, line=None, line_w=1.0):
    from pptx.enum.shapes import MSO_SHAPE
    sp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sp.shadow.inherit = False
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid(); sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line; sp.line.width = Pt(line_w)
    return sp


def text(s, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space=4):
    """runs: list of paragraphs; each paragraph = list of (txt, size, color, bold, italic)."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space)
        for (txt, size, color, bold, italic) in para:
            r = p.add_run(); r.text = txt
            r.font.size = Pt(size); r.font.color.rgb = color
            r.font.bold = bold; r.font.italic = italic
            r.font.name = "Segoe UI"
    return tb


def title_bar(s, kicker, title):
    box(s, 0.55, 0.45, 0.12, 0.7, fill=ACCENT)
    text(s, 0.85, 0.40, 11.5, 0.5, [[(kicker, 13, ACCENT, True, False)]])
    text(s, 0.85, 0.78, 11.8, 0.9, [[(title, 30, INK, True, False)]])


def pic_full(s, path, x, y, w, h):
    s.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h))


def bullets(s, x, y, w, h, items, size=15, gap=8, color=INK, marker="—", mcolor=ACCENT):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        rm = p.add_run(); rm.text = marker + "  "; rm.font.size = Pt(size); rm.font.color.rgb = mcolor; rm.font.bold = True; rm.font.name = "Segoe UI"
        if isinstance(it, tuple):
            head, rest = it
            r1 = p.add_run(); r1.text = head; r1.font.size = Pt(size); r1.font.color.rgb = INK; r1.font.bold = True; r1.font.name = "Segoe UI"
            r2 = p.add_run(); r2.text = rest; r2.font.size = Pt(size); r2.font.color.rgb = color; r2.font.name = "Segoe UI"
        else:
            r = p.add_run(); r.text = it; r.font.size = Pt(size); r.font.color.rgb = color; r.font.name = "Segoe UI"
    return tb


def table(s, x, y, w, h, data, col_w=None, header_fill=ACCENT, fs=12, hl_rows=None):
    rows, cols = len(data), len(data[0])
    gt = s.shapes.add_table(rows, cols, Inches(x), Inches(y), Inches(w), Inches(h)).table
    if col_w:
        for c, cw in enumerate(col_w):
            gt.columns[c].width = Inches(cw)
    hl_rows = hl_rows or set()
    for r in range(rows):
        for c in range(cols):
            cell = gt.cell(r, c)
            cell.margin_left = Inches(0.08); cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.03); cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            if r == 0:
                cell.fill.fore_color.rgb = RGBColor(0x10, 0x20, 0x2b)
            elif r in hl_rows:
                cell.fill.fore_color.rgb = RGBColor(0x14, 0x24, 0x18)
            else:
                cell.fill.fore_color.rgb = CARD if r % 2 else RGBColor(0x0F, 0x14, 0x1B)
            tf = cell.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
            run = p.add_run(); run.text = str(data[r][c])
            run.font.size = Pt(fs); run.font.name = "Segoe UI"
            run.font.bold = (r == 0)
            run.font.color.rgb = ACCENT if r == 0 else INK
    return gt


def footer(s, n):
    text(s, 11.6, 7.05, 1.6, 0.35, [[("Gemma4 Agent · %02d" % n, 9, MUT, False, False)]], align=PP_ALIGN.RIGHT)


# ============================================================ SLIDE 1 — PORTADA
s = slide()
box(s, 0, 0, 13.333, 7.5, fill=BG)
box(s, 0.0, 3.2, 13.333, 0.04, fill=ACCENT)
text(s, 0.9, 2.05, 11.5, 1.2, [[("Gemma4 Agent", 54, INK, True, False)]])
text(s, 0.9, 3.35, 11.6, 0.7, [[("Arquitectura de punta a punta — cómo funciona", 22, ACCENT, False, False)]])
text(s, 0.9, 4.25, 11.6, 1.4, [
    [("Asistente de voz LOCAL para Windows sobre Gemma 4 + llama.cpp.", 16, MUT, False, False)],
    [("100% offline · multi-perfil (vram3 → vram16) · voz + visión + STT en una sola caja.", 15, MUT, False, False)],
])
text(s, 0.9, 6.5, 11.6, 0.5, [[("Datos reales medidos contra el repo · 2026-05-22", 12, MUT, False, True)]])

# ============================================================ SLIDE 2 — QUÉ ES
s = slide()
title_bar(s, "VISIÓN GENERAL", "Qué es Gemma4 Agent")
bullets(s, 0.85, 1.9, 7.4, 4.6, [
    ("Voz primero. ", "wake-word ('hey gemma') → STT → el LLM razona y actúa → respuesta hablada."),
    ("100% local. ", "Gemma 4 corre en llama.cpp; STT (Whisper) en CPU; nada va a la nube."),
    ("Agente, no chatbot. ", "ejecuta acciones reales en Windows vía 65 tools (apps, ventanas, media, archivos…)."),
    ("Multi-perfil por VRAM. ", "el mismo agente escala de 3 GB a 16 GB ajustando modelo y contexto."),
    ("Seguro por diseño. ", "cada tool aislada; safety-nets que nunca tumban el turno; recovery de fallos."),
], size=15, gap=12)
# tarjeta lateral con stats
box(s, 8.7, 1.9, 3.95, 4.55, fill=CARD, line=EDGE, line_w=1.5)
text(s, 9.0, 2.1, 3.4, 4.2, [
    [("EN NÚMEROS", 13, ACCENT, True, False)],
    [("65", 30, INK, True, False)], [("tools cableadas", 12, MUT, False, False)],
    [("~55 tok/s", 24, INK, True, False)], [("decode (E4B-Q6, RTX 4060 Ti)", 11, MUT, False, False)],
    [("0.00 fp/hr", 24, PERSIST, True, False)], [("falsos wakes (302 s de ruido)", 11, MUT, False, False)],
    [("RTF 0.05", 24, INK, True, False)], [("STT 20× más rápido que realtime", 11, MUT, False, False)],
], space=2)
footer(s, 2)

# ============================================================ SLIDE 3 — HARDWARE Y PERFILES
s = slide()
title_bar(s, "HARDWARE", "Perfiles por VRAM y modelos")
data = [
    ["Perfil", "Modelo", "Quant", "Contexto", "VRAM aprox."],
    ["vram3", "Gemma 4 E2B", "Q4_K_M", "16 384", "~2.9 GB"],
    ["vram4", "Gemma 4 E4B", "Q4_K_M", "16 384", "~3.4 GB"],
    ["vram6", "Gemma 4 E4B", "Q4_K_M", "16 384", "~3.9 GB"],
    ["vram8", "Gemma 4 E4B", "Q4_K_M", "16 384", "~5.2 GB"],
    ["vram12", "Gemma 4 E4B", "Q6_K", "16 384", "~6.5 GB"],
    ["vram16", "Gemma 4 E4B", "Q6_K", "32 768", "~9.0 GB"],
]
table(s, 0.85, 1.9, 7.6, 3.9, data, col_w=[1.3, 2.3, 1.5, 1.4, 1.4], fs=12)
box(s, 8.75, 1.9, 3.9, 3.9, fill=CARD, line=EDGE, line_w=1.5)
text(s, 9.05, 2.1, 3.35, 3.6, [
    [("3 MODELOS DISTINTOS", 13, ACCENT, True, False)],
    [("E2B-Q4", 16, INK, True, False)], [("el más liviano y rápido (126 tok/s)", 11, MUT, False, False)],
    [("E4B-Q4", 16, INK, True, False)], [("equilibrio para 4–8 GB", 11, MUT, False, False)],
    [("E4B-Q6", 16, INK, True, False)], [("mejor calidad (54 tok/s)", 11, MUT, False, False)],
], space=4)
text(s, 0.85, 6.05, 11.8, 1.2, [
    [("Todos los perfiles incluyen voz + visión + STT.", 14, INK, True, False)],
    [("La voz y el STT corren en CPU (0 VRAM); el LLM ocupa la GPU. 'standby' apaga el server para liberar la GPU al jugar.", 13, MUT, False, False)],
])
footer(s, 3)

# ============================================================ SLIDE 4 — MAPA DE CAPAS
s = slide()
title_bar(s, "ARQUITECTURA", "Mapa de capas")
pic_full(s, os.path.join(ASSETS, "layers.png"), 0.5, 1.55, 12.4, 5.7)
footer(s, 4)

# ============================================================ SLIDE 5 — FLUJO DE TURNO
s = slide()
title_bar(s, "FLUJO", "Anatomía de un turno")
pic_full(s, os.path.join(ASSETS, "turn_flow.png"), 0.5, 1.55, 12.4, 5.7)
footer(s, 5)

# ============================================================ SLIDE 6 — PIPELINE DE VOZ
s = slide()
title_bar(s, "VOZ", "Pipeline always-on")
pic_full(s, os.path.join(ASSETS, "voice.png"), 0.5, 1.55, 12.4, 5.7)
footer(s, 6)

# ============================================================ SLIDE 7 — MODOS
s = slide()
title_bar(s, "RAZONAMIENTO", "El sistema de modos — ¿cuándo piensa?")
data = [
    ["Modo", "Pensar", "max_tok", "budget", "Cuándo"],
    ["fast_action", "NO", "128", "—", "smalltalk, saludos, confirmaciones"],
    ["fast_info", "NO", "320", "—", "preguntas de conocimiento (qué/cuándo/por qué)"],
    ["quick_action", "SÍ", "512", "256", "un comando ('abre Chrome')"],
    ["deep_action", "SÍ", "2048", "1024", "multi-paso ('abre X y luego Y')"],
    ["research", "SÍ", "2048", "2048", "retrieval web ('noticias actuales')"],
]
table(s, 0.85, 1.9, 11.6, 3.0, data, col_w=[2.0, 1.2, 1.3, 1.3, 5.8], fs=12, hl_rows={2})
text(s, 0.85, 5.15, 11.8, 2.0, [
    [("Clave de latencia: el LLM solo 'piensa' cuando aporta.", 16, ACCENT, True, False)],
    [("Medido: el thinking en preguntas de conocimiento era puro costo y a veces dejaba la respuesta VACÍA "
      "(el reasoning se comía el budget). fast_info (thinking OFF) las responde más rápido Y mejor.", 13.5, MUT, False, False)],
    [("Las acciones SÍ piensan: el razonamiento es lo que hace fiable el tool-call (2/6 → 6/6).", 13.5, MUT, False, False)],
])
footer(s, 7)

# ============================================================ SLIDE 8 — DISPATCH + VERIFIERS
s = slide()
title_bar(s, "EJECUCIÓN", "Dispatch de tools + verifiers (blast radius)")
bullets(s, 0.85, 1.9, 7.5, 4.8, [
    ("Doble contención. ", "cada tool corre dentro de try/except en execute() Y dentro de _run_with_timeout(). Una tool que crashea o cuelga se vuelve {ok:False} — NUNCA aborta el turno."),
    ("Timeout por modo. ", "el LLM tiene deadline derivado del presupuesto de tokens (20–150 s); un turno colgado falla rápido en vez de freezar minutos."),
    ("Verifier por tool. ", "verify_core mide el efecto real; si crashea devuelve confirmed=False, jamás propaga."),
    ("Loop-detector. ", "corta repeticiones; endurecido para no crashear con args de tipos mixtos."),
    ("Honestidad. ", "guards de grounding/promise reescriben un 'Listo' falso si la acción no ocurrió."),
], size=14, gap=11)
box(s, 8.7, 1.9, 3.95, 4.55, fill=CARD, line=HOT, line_w=1.8)
text(s, 9.0, 2.15, 3.4, 4.1, [
    [("INVARIANTE", 13, HOT, True, False)],
    [("El turno NUNCA:", 14, INK, True, False)],
    [("· crashea", 13, MUT, False, False)],
    [("· pierde un reply ya generado", 13, MUT, False, False)],
    [("· corrompe persistencia", 13, MUT, False, False)],
    [("· deja procesos huérfanos", 13, MUT, False, False)],
    [("· miente sobre su estado", 13, MUT, False, False)],
], space=6)
footer(s, 8)

# ============================================================ SLIDE 9 — PERSISTENCIA Y RECOVERY
s = slide()
title_bar(s, "FIABILIDAD", "Persistencia y recovery")
bullets(s, 0.85, 1.9, 11.7, 4.6, [
    ("Escritura atómica. ", "state y sessions usan os.replace — nunca queda un JSON truncado a medio escribir."),
    ("Cuarentena de DB. ", "si experience.sqlite se corrompe (corte de luz / sync) se aísla en .corrupt-<ts> y se recrea: la memoria 'arranca de cero', no se rompe para siempre."),
    ("Rotación acotada. ", "telemetry poda filas > 30 días una vez por proceso (medido: poda 50k en 49 ms; queries siguen < 16 ms)."),
    ("Descarga atómica. ", "las voces de Piper se bajan a un .part y se renombran al terminar: un corte de red no deja un .onnx corrupto."),
    ("Sin huérfanos. ", "el llama-server se detiene en atexit (no queda reteniendo 6 GB de VRAM); nunca mata un server externo del usuario."),
    ("Visión lazy. ", "el preset de visión se carga on-demand al llegar una imagen — sin error 'mmproj', en todos los perfiles."),
], size=14, gap=10)
footer(s, 9)

# ============================================================ SLIDE 10 — LATENCIA (chart + cross-profile)
s = slide()
title_bar(s, "LATENCIA", "Antes / después — el big win (fast_info)")
pic_full(s, os.path.join(ASSETS, "latency.png"), 0.5, 1.5, 7.55, 5.0)
text(s, 8.25, 1.7, 4.5, 0.8, [[("Validado en los 3 modelos", 15, ACCENT, True, False)]])
data = [
    ["Perfil", "Modelo", "Preguntas"],
    ["vram3", "E2B-Q4", "0.30 s"],
    ["vram4/6/8", "E4B-Q4", "0.48 s"],
    ["vram12/16", "E4B-Q6", "0.58 s"],
]
table(s, 8.25, 2.45, 4.45, 1.7, data, col_w=[1.5, 1.5, 1.45], fs=12)
text(s, 8.25, 4.45, 4.5, 2.7, [
    [("median corpus  4.00 → 1.90 s", 14, INK, True, False)],
    [("max  48.2 → 11.6 s", 14, INK, True, False)],
    [("calidad  0.959 → 0.989  (subió)", 14, PERSIST, True, False)],
    [("Las 16 preguntas, en TODOS los perfiles: < 1.1 s, 0 lentas, 0 incorrectas.", 12.5, MUT, False, False)],
])
footer(s, 10)

# ============================================================ SLIDE 11 — VEREDICTO
s = slide()
title_bar(s, "ESTADO", "Veredicto e invariantes")
box(s, 0.85, 1.85, 5.7, 4.7, fill=CARD, line=EDGE, line_w=1.5)
text(s, 1.15, 2.1, 5.1, 4.2, [
    [("CONSOLIDADO", 15, PERSIST, True, False)],
    [("27 bugs + 2 optimizaciones de latencia", 14, INK, True, False)],
    [("en 13 rondas de auditoría", 12, MUT, False, False)],
    [("", 6, MUT, False, False)],
    [("Guardrails durables:", 13, ACCENT, True, False)],
    [("· perf budget (latencia)", 12.5, MUT, False, False)],
    [("· invariantes arquitectónicos", 12.5, MUT, False, False)],
    [("· no-orphan + fuzz de primitivos", 12.5, MUT, False, False)],
    [("· smoke por perfil (3 modelos)", 12.5, MUT, False, False)],
], space=5)
box(s, 6.95, 1.85, 5.7, 4.7, fill=CARD, line=ACCENT, line_w=1.5)
text(s, 7.25, 2.1, 5.1, 4.2, [
    [("CONFIANZA POR EJE", 15, ACCENT, True, False)],
    [("Arquitectura", 14, INK, True, False)], [("hot-path limpio, singletons con lock — Alta", 12, MUT, False, False)],
    [("Fiabilidad", 14, INK, True, False)], [("recovery, teardown, fuzz — Alta", 12, MUT, False, False)],
    [("Latencia", 14, INK, True, False)], [("preguntas < 1.1 s en todos los perfiles — Alta", 12, MUT, False, False)],
    [("", 6, MUT, False, False)],
    [("Patrón confirmado 9×: los bugs vivieron en los bordes, no en el camino feliz.", 12.5, PERSIST, False, True)],
], space=4)
text(s, 0.85, 6.75, 11.8, 0.5, [[("Rama lista para review. Multistep real (N tool-calls) sigue > 5 s por diseño.", 12.5, MUT, False, True)]])
footer(s, 11)

out = os.path.join(HERE, "Gemma4_Agent_Arquitectura.pptx")
prs.save(out)
print("SAVED:", out, "·", len(prs.slides._sldIdLst), "slides")
