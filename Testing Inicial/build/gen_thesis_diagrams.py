"""Diagramas referenciales para la PRESENTACIÓN DE TESIS de Gemma4 Agent.

Genera PNG de alta resolución con paleta oscura técnica coherente, pensados
para slides de pitch (yo hablo encima): poco texto, una idea por imagen.

NO son los diagramas de arquitectura interna (esos viven en gen_diagrams.py);
estos cuentan la HISTORIA de la tesis: posicionamiento, flujo de un turno,
pipeline de voz, capacidades, veredicto de viabilidad.

Datos REALES verificados contra el código y los reportes (2026-05-22):
- modes.py: fast_action 128/OFF, fast_info 320/OFF, quick 512/256, deep 2048/1024
- bench/llm_e2e_validation.md: TTFT 22-73ms, decode ~55 tok/s (E4B-Q6)
- bench/latency_sprint_report.md: preguntas <1.1s, acciones ~2-4s, multistep 9-11s
- tool_schemas.COMPOUND_TOOL_SCHEMAS: 65 tools
"""
from __future__ import annotations

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
from matplotlib.lines import Line2D

# ---- Paleta (oscuro técnico) ----------------------------------------------
BG      = "#0A0E14"   # fondo
PANEL   = "#141A24"   # cajas
PANEL2  = "#1C2430"   # cajas alt
STROKE  = "#2A3340"   # bordes
INK     = "#E6EDF3"   # texto principal
MUTE    = "#8B98A8"   # texto secundario
ACCENT  = "#5BC8FF"   # cyan  — Gemma4 / hot-path
VIOLET  = "#9D7CFF"   # violeta — voz/audio
GREEN   = "#3FB950"   # verde — éxito/local/viable
ORANGE  = "#FF7A59"   # naranja — acento cálido / acción
YELLOW  = "#E3B341"   # amarillo — atención/futuro
RED     = "#F85149"   # rojo — limitación

ASSETS = os.path.join(os.path.dirname(__file__), "pptx_assets")
os.makedirs(ASSETS, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 13,
})


def _fig(w=13.33, h=6.4):
    fig = plt.figure(figsize=(w, h), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100 * h / w)
    ax.axis("off")
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    return fig, ax, 100 * h / w


def _box(ax, x, y, w, h, label, *, fc=PANEL, ec=STROKE, tc=INK,
         fs=13, bold=False, lw=1.4, sub=None, sub_c=None, round_=0.025, align="center"):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={round_*100}",
        linewidth=lw, edgecolor=ec, facecolor=fc, mutation_aspect=1))
    cx = x + w / 2 if align == "center" else x + w * 0.06
    ha = "center" if align == "center" else "left"
    if sub:
        ax.text(cx, y + h * 0.60, label, ha=ha, va="center", color=tc,
                fontsize=fs, fontweight="bold" if bold else "normal")
        ax.text(cx, y + h * 0.27, sub, ha=ha, va="center",
                color=sub_c or MUTE, fontsize=fs - 3)
    else:
        ax.text(cx, y + h / 2, label, ha=ha, va="center", color=tc,
                fontsize=fs, fontweight="bold" if bold else "normal")


def _arrow(ax, x1, y1, x2, y2, c=ACCENT, lw=2.2, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle=style, mutation_scale=18,
        linewidth=lw, color=c, linestyle=ls,
        shrinkA=2, shrinkB=2, joinstyle="miter"))


def _chip(ax, cx, cy, txt, c=ACCENT, fs=11):
    ax.text(cx, cy, txt, ha="center", va="center", color=c, fontsize=fs,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.4", fc=PANEL2, ec=c, lw=1.2))


# ===========================================================================
# 1. POSICIONAMIENTO — Gemma4 vs Alexa vs Claude Code (cuadrante)
# ===========================================================================
def diagram_positioning():
    """Tres tarjetas comparativas (sin Venn solapado): cada competidor con sus
    atributos en filas alineadas. La de Gemma4 destacada."""
    fig, ax, H = _fig(13.33, 6.2)
    cards = [
        ("Alexa · Siri · Cortana", YELLOW, [
            ("Fácil de usar", True),
            ("Local / privado", False),
            ("Controla TU PC", False),
            ("Sin suscripción", True),
            ("LLM potente", False),
        ]),
        ("Claude Code · Cowork", VIOLET, [
            ("Fácil de usar", False),
            ("Local / privado", False),
            ("Controla TU PC", True),
            ("Sin suscripción", False),
            ("LLM potente", True),
        ]),
        ("Gemma4 Agent", GREEN, [
            ("Fácil de usar", True),
            ("Local / privado", True),
            ("Controla TU PC", True),
            ("Sin suscripción", True),
            ("LLM potente", True),
        ]),
    ]
    n = len(cards)
    cw = 27
    gap = (100 - 8 - n * cw) / (n - 1)
    cardh = H - 6
    y = 1.5
    nrows = len(cards[0][2])
    for i, (name, c, rows) in enumerate(cards):
        x = 4 + i * (cw + gap)
        highlight = (name.startswith("Gemma4"))
        ax.add_patch(FancyBboxPatch((x, y), cw, cardh,
                     boxstyle="round,pad=0,rounding_size=1.2",
                     fc=PANEL2 if highlight else PANEL,
                     ec=c, lw=3.2 if highlight else 1.6))
        # header
        ax.text(x + cw / 2, y + cardh - 3.6, name, ha="center", va="center",
                color=INK, fontsize=12.5 if not highlight else 13.5,
                fontweight="bold")
        ax.add_line(Line2D([x + 3, x + cw - 3], [y + cardh - 6.8, y + cardh - 6.8],
                    color=STROKE, lw=1))
        # rows — repartidas en el espacio disponible (header arriba, estrella abajo)
        area_top = y + cardh - 9.5
        area_bot = y + (5.5 if highlight else 3.0)
        step = (area_top - area_bot) / (nrows - 1)
        for j, (label, ok) in enumerate(rows):
            ry = area_top - j * step
            mark = "✓" if ok else "✕"
            mc = GREEN if ok else RED
            ax.text(x + 4.0, ry, mark, ha="center", va="center", color=mc,
                    fontsize=13, fontweight="bold")
            ax.text(x + 7.0, ry, label, ha="left", va="center",
                    color=INK if ok else MUTE, fontsize=10.8)
        if highlight:
            ax.text(x + cw / 2, y + 2.3, "★ instalar y listo", ha="center",
                    color=c, fontsize=11.5, fontweight="bold")
    fig.savefig(os.path.join(ASSETS, "positioning.png"), facecolor=BG)
    plt.close(fig)


# ===========================================================================
# 2. FLUJO DE UN TURNO (referencial, limpio)
# ===========================================================================
def diagram_turn_flow():
    fig, ax, H = _fig(13.33, 5.4)
    steps = [
        ("Hablás", "“abre Spotify”", VIOLET),
        ("Wake +\nVAD", "detecta voz", VIOLET),
        ("STT", "Whisper · CPU\nRTF 0.05", ACCENT),
        ("LLM local", "Gemma 4\nrutea + decide", ACCENT),
        ("Acción", "65 tools\nejecuta en Windows", ORANGE),
        ("Confirma", "por voz\n(Piper TTS)", GREEN),
    ]
    n = len(steps)
    bw, bh = 13.2, 17
    gap = (100 - 8 - n * bw) / (n - 1)
    y = H / 2 - bh / 2
    xs = []
    for i, (t, s, c) in enumerate(steps):
        x = 4 + i * (bw + gap)
        xs.append(x)
        _box(ax, x, y, bw, bh, t, sub=s, fc=PANEL, ec=c, tc=INK, bold=True,
             fs=13, round_=0.05, sub_c=MUTE)
        # número
        ax.add_patch(Circle((x + 2.4, y + bh - 2.4), 1.7, fc=c, ec="none"))
        ax.text(x + 2.4, y + bh - 2.4, str(i + 1), ha="center", va="center",
                color=BG, fontsize=11, fontweight="bold")
    for i in range(n - 1):
        _arrow(ax, xs[i] + bw, y + bh / 2, xs[i + 1], y + bh / 2,
               c=STROKE, lw=2.4)
    # franja: todo local
    ax.text(50, y - 5.5, "TODO corre en tu PC — sin nube, sin enviar tu voz a internet",
            ha="center", color=GREEN, fontsize=12.5, fontweight="bold")
    fig.savefig(os.path.join(ASSETS, "turn_flow.png"), facecolor=BG)
    plt.close(fig)


# ===========================================================================
# 3. PIPELINE DE VOZ con latencias reales
# ===========================================================================
def diagram_voice():
    fig, ax, H = _fig(13.33, 5.6)
    blocks = [
        ("Micrófono", "audio_io", MUTE, ""),
        ("VAD + Wake", "Silero + LiveKit ONNX\n8 Hz · 0.00 FP/h", VIOLET, ""),
        ("STT", "faster-whisper small\nCPU int8 · RTF 0.05", ACCENT, ""),
        ("LLM local", "Gemma 4 · llama.cpp\nTTFT 22-73 ms · ~55 tok/s", ACCENT, ""),
        ("TTS", "Piper · streaming\nempieza a hablar pronto", VIOLET, ""),
    ]
    n = len(blocks)
    bw, bh = 16.5, 18
    gap = (100 - 8 - n * bw) / (n - 1)
    y = H / 2 - bh / 2 + 2
    xs = []
    for i, (t, s, c, _) in enumerate(blocks):
        x = 4 + i * (bw + gap)
        xs.append(x)
        _box(ax, x, y, bw, bh, t, sub=s, fc=PANEL, ec=c, tc=INK, bold=True,
             fs=13, round_=0.05, sub_c=MUTE)
    for i in range(n - 1):
        _arrow(ax, xs[i] + bw, y + bh / 2, xs[i + 1], y + bh / 2, c=STROKE, lw=2.4)

    # barra de presupuesto de latencia
    by = y - 9
    ax.text(50, by + 3.0, "Presupuesto de voz: 4–5 s por turno  ·  preguntas medidas < 1.1 s",
            ha="center", color=INK, fontsize=12, fontweight="bold")
    # mini barra
    bx0, bx1, bbh = 22, 78, 2.2
    ax.add_patch(FancyBboxPatch((bx0, by - 3), bx1 - bx0, bbh,
                 boxstyle="round,pad=0,rounding_size=1", fc=PANEL2, ec=STROKE, lw=1))
    frac = 1.1 / 5.0
    ax.add_patch(FancyBboxPatch((bx0, by - 3), (bx1 - bx0) * frac, bbh,
                 boxstyle="round,pad=0,rounding_size=1", fc=GREEN, ec="none"))
    ax.text(bx0, by - 5.0, "0 s", color=MUTE, fontsize=9, ha="center")
    ax.text(bx1, by - 5.0, "5 s (tope)", color=MUTE, fontsize=9, ha="center")
    fig.savefig(os.path.join(ASSETS, "voice.png"), facecolor=BG)
    plt.close(fig)


# ===========================================================================
# 4. CAPACIDADES — 65 tools agrupados
# ===========================================================================
def diagram_capabilities():
    fig, ax, H = _fig(13.33, 5.7)
    groups = [
        ("Apps y ventanas", "abrir/cerrar · minimizar · Steam · juegos", ORANGE, 6),
        ("Sistema y control", "volumen · red · dispositivos · paquetes", ACCENT, 12),
        ("Voz · visión · GUI", "screenshots · UIA · accesibilidad · vision", VIOLET, 5),
        ("Web y conocimiento", "buscar · navegar · fact-check · fuentes", ACCENT, 8),
        ("Multimedia", "media · edición · fotos · impresora", VIOLET, 5),
        ("Productividad", "notas · recordatorios · calendario · WhatsApp · email", GREEN, 11),
        ("Datos y dev", "terminal · archivos · base de datos · descargas", MUTE, 10),
        ("Memoria y estado", "memoria · skills · subagentes · rutinas", YELLOW, 8),
    ]
    cols, rows = 4, 2
    mx, my = 4, 8
    cw = (100 - 2 * mx - (cols - 1) * 2.5) / cols
    ch = (H - 2 * my - (rows - 1) * 3 - 6) / rows
    i = 0
    for r in range(rows):
        for c in range(cols):
            name, sub, col, cnt = groups[i]
            x = mx + c * (cw + 2.5)
            y = my + (rows - 1 - r) * (ch + 3)
            ax.add_patch(FancyBboxPatch((x, y), cw, ch,
                         boxstyle="round,pad=0,rounding_size=1.2",
                         fc=PANEL, ec=col, lw=1.6))
            ax.text(x + cw / 2, y + ch - 4.0, name, ha="center", color=INK,
                    fontsize=12.5, fontweight="bold")
            # count chip
            ax.text(x + cw / 2, y + ch - 9.5, f"{cnt} tools", ha="center",
                    color=col, fontsize=10.5, fontweight="bold")
            ax.text(x + cw / 2, y + 4.0, sub, ha="center", color=MUTE,
                    fontsize=8.6, wrap=True)
            i += 1
    ax.text(50, H - 3.0, "65 herramientas — el agente elige la correcta por cada pedido",
            ha="center", color=ACCENT, fontsize=13, fontweight="bold")
    fig.savefig(os.path.join(ASSETS, "capabilities.png"), facecolor=BG)
    plt.close(fig)


# ===========================================================================
# 5. VIABILIDAD — gauge de latencia por tipo de turno
# ===========================================================================
def diagram_viability():
    fig, ax, H = _fig(13.33, 6.4)
    cap = 5.0  # tope de presupuesto
    rows = [
        ("Saludo / smalltalk", 0.73, GREEN),
        ("Pregunta de conocimiento", 1.1, GREEN),
        ("Acción (abrir app, volumen)", 3.5, GREEN),
        ("Multi-acción (3 cosas)", 10.0, YELLOW),
    ]
    x0 = 31
    x1 = 92
    bh = 5.0
    top = H - 11
    span = x1 - x0
    scale_max = 12.0  # escala 0..12 s
    # marcador del tope de presupuesto (5 s)
    cap_x = x0 + span * (cap / scale_max)
    bottom_axis = 8.0
    ax.add_line(Line2D([cap_x, cap_x], [bottom_axis, top + bh + 1.5], color=RED, lw=1.8, ls="--"))
    ax.text(cap_x, top + bh + 3.0, "tope voz 5 s", color=RED, fontsize=10.5,
            ha="center", fontweight="bold")
    for i, (name, val, c) in enumerate(rows):
        y = top - i * (bh + 4.3)
        ax.text(x0 - 2.5, y + bh / 2, name, ha="right", va="center", color=INK, fontsize=12)
        ax.add_patch(FancyBboxPatch((x0, y), span, bh,
                     boxstyle="round,pad=0,rounding_size=1", fc=PANEL2, ec=STROKE, lw=1))
        fw = span * min(val, scale_max) / scale_max
        ax.add_patch(FancyBboxPatch((x0, y), fw, bh,
                     boxstyle="round,pad=0,rounding_size=1", fc=c, ec="none"))
        ax.text(x0 + fw + 1.8, y + bh / 2, f"{val:g} s", ha="left", va="center",
                color=c, fontsize=12, fontweight="bold")
    # eje X con ticks correctos
    for tick in (0, 4, 8, 12):
        tx = x0 + span * tick / scale_max
        ax.add_line(Line2D([tx, tx], [bottom_axis, bottom_axis + 0.8], color=MUTE, lw=1))
        ax.text(tx, bottom_axis - 1.6, f"{tick} s", color=MUTE, fontsize=9, ha="center")
    ax.add_line(Line2D([x0, x1], [bottom_axis, bottom_axis], color=STROKE, lw=1))
    fig.savefig(os.path.join(ASSETS, "viability.png"), facecolor=BG)
    plt.close(fig)


if __name__ == "__main__":
    diagram_positioning()
    diagram_turn_flow()
    diagram_voice()
    diagram_capabilities()
    diagram_viability()
    print("OK — diagramas en", ASSETS)
