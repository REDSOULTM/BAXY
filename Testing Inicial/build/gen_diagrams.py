"""Genera los diagramas de la presentación (PNG de alta resolución) con matplotlib.
Datos REALES verificados contra el repo. Paleta técnica oscura coherente con la UI."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D
import os

OUT = os.path.join(os.path.dirname(__file__), "pptx_assets")
os.makedirs(OUT, exist_ok=True)

# Paleta
BG = "#0A0E14"
INK = "#E6EDF3"
MUT = "#8B97A7"
ACCENT = "#5BC8FF"     # cyan
HOT = "#FF7A59"        # naranja (hot-path)
AUDIO = "#7C5CFF"      # violeta (always-on audio)
PERSIST = "#3FB950"    # verde (persistencia)
DIAG = "#D29922"       # amarillo (diagnósticos)
CARD = "#141A23"
EDGE = "#2A3441"

plt.rcParams["font.family"] = "DejaVu Sans"


def _box(ax, x, y, w, h, text, fc=CARD, ec=EDGE, tc=INK, fs=11, bold=False, lw=1.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                fc=fc, ec=ec, lw=lw, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tc,
            fontsize=fs, fontweight="bold" if bold else "normal", zorder=3, wrap=True)


def _arrow(ax, x1, y1, x2, y2, color=MUT, lw=2.0, style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                 mutation_scale=16, color=color, lw=lw, zorder=1,
                 connectionstyle="arc3,rad=0"))


def fig(w=13.33, h=7.5):
    f, ax = plt.subplots(figsize=(w, h), dpi=150)
    f.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return f, ax


# ---------------------------------------------------------------- 1. MAPA DE CAPAS
def diagram_layers():
    f, ax = fig()
    ax.text(50, 96, "Mapa de capas — Gemma4 Agent", ha="center", color=INK, fontsize=22, fontweight="bold")
    ax.text(50, 91.5, "Patrón verificado: los 27 bugs vivieron en los BORDES, nunca en el camino feliz",
            ha="center", color=MUT, fontsize=12, style="italic")

    # Superficies (entrada)
    _box(ax, 6, 80, 88, 7, "SUPERFICIES   ·   launcher.py  ·  server.py (FastAPI/uvicorn)  ·  chat.py (CLI)  ·  mcp_server.py",
         fc="#10202b", ec=ACCENT, tc=ACCENT, fs=12, bold=True)

    # Always-on audio (izquierda): contenedor 42-78, título arriba, sub-boxes debajo
    _box(ax, 5, 42, 27, 36, "", fc="#160f28", ec=AUDIO, lw=1.8)
    ax.text(18.5, 75.6, "ALWAYS-ON AUDIO", ha="center", color=AUDIO, fontsize=12, fontweight="bold")
    for i, t in enumerate(["audio_io (callback no-bloq.)", "VAD (Silero)", "wake (LiveKit ONNX · 8 Hz)", "pipeline (state machine)", "TTS Piper → parlantes"]):
        _box(ax, 6.5, 68.5 - i * 5.3, 24, 4.3, t, fc=CARD, ec=AUDIO, tc=INK, fs=9.5)

    # Hot-path turno (centro)
    _box(ax, 36, 42, 30, 36, "", fc="#24140e", ec=HOT, lw=1.8)
    ax.text(51, 75.6, "HOT-PATH DEL TURNO  ·  run_content", ha="center", color=HOT, fontsize=11.5, fontweight="bold")
    for i, t in enumerate(["choose_mode (gating thinking)", "router (intent + semántico)", "_system_message (prompt slim)", "LLM call (timeout per-mode)", "dispatch tools (try/except ×2)", "verifiers (per-tool)"]):
        _box(ax, 37.5, 69.0 - i * 4.55, 27, 3.7, t, fc=CARD, ec=HOT, tc=INK, fs=9.5)

    # Persistencia (derecha arriba)
    _box(ax, 70, 61, 24, 17, "", fc="#0d2014", ec=PERSIST, lw=1.8)
    ax.text(82, 75.6, "PERSISTENCIA", ha="center", color=PERSIST, fontsize=12, fontweight="bold")
    for i, t in enumerate(["state · atómica", "experience · cuarentena", "telemetry · rotación", "sessions"]):
        _box(ax, 71.3, 68.5 - i * 3.3, 21.4, 2.8, t, fc=CARD, ec=PERSIST, tc=INK, fs=9)

    # Diagnósticos (derecha abajo)
    _box(ax, 70, 42, 24, 17, "", fc="#241e0a", ec=DIAG, lw=1.8)
    ax.text(82, 56.6, "DIAGNÓSTICOS (fail-safe)", ha="center", color=DIAG, fontsize=11, fontweight="bold")
    for i, t in enumerate(["tracing", "log_recorder", "loop_detection", "EventBus"]):
        _box(ax, 71.3, 49.5 - i * 3.3, 21.4, 2.8, t, fc=CARD, ec=DIAG, tc=INK, fs=9)

    # Daemons / lifecycle (banda inferior)
    _box(ax, 6, 30, 88, 9, "DAEMONS / LIFECYCLE   ·   LlamaServerManager (atexit, locks)  ·  profile_watcher  ·  agent_runner boot  ·  boot_progress",
         fc="#161616", ec=MUT, tc=MUT, fs=11, bold=True)

    # llama.cpp server
    _box(ax, 30, 16, 40, 8, "llama.cpp server (router mode)\n<perfil>-text  +  <perfil>-vision (lazy)", fc="#10202b", ec=ACCENT, tc=ACCENT, fs=11, bold=True)

    # flechas
    _arrow(ax, 50, 80, 51, 78, ACCENT)           # superficies -> hot-path
    _arrow(ax, 18.5, 42, 18.5, 39, AUDIO)        # audio -> lifecycle
    _arrow(ax, 51, 42, 51, 39, HOT)              # turno -> lifecycle
    _arrow(ax, 82, 42, 60, 39, PERSIST, lw=1.4)  # persistencia/diag -> lifecycle
    _arrow(ax, 50, 30, 50, 24, ACCENT)           # lifecycle -> server
    _arrow(ax, 32.5, 60, 36, 60, ACCENT, lw=1.6) # audio command -> turno

    # leyenda invariantes
    leg = [("Hot-path: blast radius contenido (try/except × tool)", HOT),
           ("Always-on: callback nunca bloquea; wake decimado", AUDIO),
           ("Persistencia: atómica + recovery de corrupción", PERSIST),
           ("Diagnóstico: nunca crashea lo que observa", DIAG)]
    for i, (t, c) in enumerate(leg):
        ax.add_patch(FancyBboxPatch((7 + i * 23, 7.5), 0.8, 2.0, boxstyle="round", fc=c, ec=c))
        ax.text(8.2 + i * 23, 8.5, t, color=MUT, fontsize=7.4, va="center")

    f.savefig(os.path.join(OUT, "layers.png"), facecolor=BG, bbox_inches="tight", pad_inches=0.25)
    plt.close(f)


# ---------------------------------------------------------------- 2. FLUJO DE TURNO
def diagram_turn_flow():
    f, ax = fig()
    ax.text(50, 96, "Flujo de un turno (voz → respuesta)", ha="center", color=INK, fontsize=22, fontweight="bold")
    ax.text(50, 91.5, "Cada flecha que cruza a proceso/disco/modelo tiene su contención: timeout, try/except o recovery",
            ha="center", color=MUT, fontsize=11.5, style="italic")

    # Fila always-on audio
    steps_audio = [("audio_io", AUDIO), ("VAD\n(gate voz)", AUDIO), ("wake\n'hey gemma'", AUDIO),
                   ("STT Whisper\nRTF 0.05", AUDIO), ("corrector\nfuzzy", AUDIO)]
    x = 4
    for i, (t, c) in enumerate(steps_audio):
        _box(ax, x, 74, 15, 9, t, fc=CARD, ec=c, tc=INK, fs=10, bold=True)
        if i < len(steps_audio) - 1:
            _arrow(ax, x + 15, 78.5, x + 18, 78.5, c)
        x += 18
    ax.text(4, 85, "ENTRADA DE VOZ (always-on, CPU)", color=AUDIO, fontsize=11, fontweight="bold")

    # baja al turno
    _arrow(ax, 50, 74, 50, 66, ACCENT, lw=2.4)
    ax.text(53, 70, "texto del comando", color=MUT, fontsize=9, style="italic")

    # Fila hot-path turno
    steps_turn = [("choose_mode\n¿piensa?", HOT), ("router\nintent+semántico", HOT),
                  ("_system_message\nprompt slim", HOT), ("LLM\ntimeout per-mode", HOT)]
    x = 8
    for i, (t, c) in enumerate(steps_turn):
        _box(ax, x, 52, 17, 10, t, fc=CARD, ec=c, tc=INK, fs=10, bold=True)
        if i < len(steps_turn) - 1:
            _arrow(ax, x + 17, 57, x + 20, 57, c)
        x += 20
    ax.text(8, 64, "HOT-PATH DEL TURNO", color=HOT, fontsize=11, fontweight="bold")

    # decisión: tool?
    ax.add_patch(FancyBboxPatch((40, 36), 20, 9, boxstyle="round,pad=0.02,rounding_size=0.03",
                                fc="#2a1812", ec=HOT, lw=2))
    ax.text(50, 40.5, "¿tool_calls?", ha="center", va="center", color=HOT, fontsize=12, fontweight="bold")
    _arrow(ax, 50, 52, 50, 45, HOT)

    # rama tool
    _box(ax, 8, 24, 22, 8, "dispatch tool\n_run_with_timeout (try/except)", fc=CARD, ec=HOT, tc=INK, fs=9.5)
    _box(ax, 8, 14, 22, 7, "verifier per-tool\nconfirmed F/None, nunca crashea", fc=CARD, ec=PERSIST, tc=INK, fs=9)
    _arrow(ax, 42, 38, 30, 28, HOT)
    ax.text(33, 34, "SÍ", color=HOT, fontsize=10, fontweight="bold")
    _arrow(ax, 19, 24, 19, 21, HOT)
    _arrow(ax, 19, 14, 40, 30, MUT, lw=1.4)   # loop back
    ax.text(28, 19, "loop (máx N turns,\nloop-detector)", color=MUT, fontsize=8)

    # rama reply
    _box(ax, 64, 24, 30, 8, "sanitize_text  ·  guards (grounding/promise)\nmission footer (no destruye reply)", fc=CARD, ec=ACCENT, tc=INK, fs=9)
    _arrow(ax, 58, 38, 78, 32, ACCENT)
    ax.text(64, 35, "NO → reply", color=ACCENT, fontsize=10, fontweight="bold")
    _box(ax, 64, 13, 30, 8, "AgentReply  →  TTS (Piper)\nfeed_tts + flush_tts", fc="#1a1430", ec=AUDIO, tc=INK, fs=10, bold=True)
    _arrow(ax, 79, 24, 79, 21, AUDIO)

    f.savefig(os.path.join(OUT, "turn_flow.png"), facecolor=BG, bbox_inches="tight", pad_inches=0.25)
    plt.close(f)


# ---------------------------------------------------------------- 3. PIPELINE DE VOZ
def diagram_voice():
    f, ax = fig()
    ax.text(50, 96, "Pipeline de voz — latencias reales", ha="center", color=INK, fontsize=22, fontweight="bold")
    ax.text(50, 91.5, "Wake LiveKit (ONNX) + faster-whisper (CPU int8) + Piper TTS — medido contra audio real",
            ha="center", color=MUT, fontsize=11.5, style="italic")

    blocks = [
        ("Micrófono\naudio_io", "callback solo copy+put_nowait\n(nunca bloquea el audio thread)", AUDIO),
        ("VAD Silero", "gate de voz, torch 1-thread", AUDIO),
        ("Wake LiveKit\nONNX", "'hey gemma' · throttle 8 Hz\n0 falsos / 302 s ruido (0.00 fp/hr)\n19% de un core (−74% CPU)", ACCENT),
        ("STT faster-whisper\nsmall · CPU int8", "RTF 0.05 (293 s → 15 s)\n20× más rápido que realtime", PERSIST),
        ("Corrector fuzzy\n(RapidFuzz)", "'cromo'→Chrome, conservador", DIAG),
        ("Piper TTS\nstreaming", "first-chunk flush + tail-grace\nanti self-hearing", HOT),
    ]
    y = 78
    for i, (title, sub, c) in enumerate(blocks):
        _box(ax, 10, y - 9, 30, 8.5, title, fc=CARD, ec=c, tc=c, fs=12, bold=True)
        ax.text(43, y - 4.7, sub, color=INK, fontsize=10, va="center")
        if i < len(blocks) - 1:
            _arrow(ax, 25, y - 9, 25, y - 11.5, c, lw=2.2)
        y -= 12.2

    f.savefig(os.path.join(OUT, "voice.png"), facecolor=BG, bbox_inches="tight", pad_inches=0.25)
    plt.close(f)


# ---------------------------------------------------------------- 4. LATENCIA antes/después
def chart_latency():
    f, ax = plt.subplots(figsize=(13.33, 7.0), dpi=150)
    f.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    tipos = ["smalltalk", "factual", "pregunta\ncompleja", "acción", "multistep", "research"]
    base = [0.78, 0.59, 2.27, 6.17, 10.98, 6.84]
    final = [0.73, 0.60, 1.25, 5.34, 9.29, 7.37]
    import numpy as np
    x = np.arange(len(tipos)); w = 0.38
    b1 = ax.bar(x - w / 2, base, w, label="Baseline", color="#3a4654", edgecolor=EDGE)
    b2 = ax.bar(x + w / 2, final, w, label="Tras fast_info", color=ACCENT, edgecolor=EDGE)
    ax.axhline(5.0, color=HOT, ls="--", lw=2, label="Budget voz (5 s)")
    for bars in (b1, b2):
        for r in bars:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.15, f"{r.get_height():.1f}",
                    ha="center", color=INK, fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(tipos, color=INK, fontsize=11)
    ax.set_ylabel("Latencia mediana (s)", color=INK, fontsize=12)
    ax.set_title("Latencia por tipo de turno — median del corpus 4.00 s → 1.90 s",
                 color=INK, fontsize=16, fontweight="bold", pad=14)
    ax.tick_params(colors=MUT)
    for s in ax.spines.values():
        s.set_color(EDGE)
    ax.legend(facecolor=CARD, edgecolor=EDGE, labelcolor=INK, fontsize=11, loc="upper left")
    ax.grid(axis="y", color=EDGE, alpha=0.4)
    f.savefig(os.path.join(OUT, "latency.png"), facecolor=BG, bbox_inches="tight", pad_inches=0.2)
    plt.close(f)


diagram_layers()
diagram_turn_flow()
diagram_voice()
chart_latency()
print("OK diagrams:", os.listdir(OUT))
