"""Left/right side panels, header bar, footer.

The left panel hosts SysMonitor (metrics) + status badges + tool subset.
The right panel hosts ActivityLog + input row + drop zone + actions.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from . import metrics as metrics_mod
from .metric_bar import MetricBar
from .theme import C, button_qss, display, line_edit_qss, mono, panel_qss


_LEFT_W = 168
_RIGHT_W = 360


# ---------------------------------------------------------------------------
def build_header() -> tuple[QWidget, dict[str, Any]]:
    w = QWidget()
    # Altura total = 58 (linea principal) + 22 (banner condicional). Cuando
    # el banner esta oculto no consume el alto extra porque le ponemos
    # setVisible(False); el layout se reajusta solo.
    w.setStyleSheet(f"background: {C.DARK}; border-bottom: 1px solid {C.BORDER_B};")
    outer = QVBoxLayout(w)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    top = QWidget()
    top.setFixedHeight(58)
    top.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(top)
    lay.setContentsMargins(16, 0, 16, 0)

    def _lbl(txt: str, color: str = C.TEXT_MED, font_size: int = 8) -> QLabel:
        l = QLabel(txt)
        l.setFont(mono(font_size))
        l.setStyleSheet(f"color: {color}; background: transparent;")
        return l

    left_brand = _lbl("MARK I  ·  GEMMA4", C.PRI_DIM, 9)
    lay.addWidget(left_brand)
    lay.addStretch()

    mid = QVBoxLayout()
    mid.setSpacing(0)
    title = QLabel("G E M M A 4")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setFont(display(17, True))
    title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
    mid.addWidget(title)
    sub = QLabel("Local. Multimodal. Just A Rather Very Intelligent System.")
    sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
    sub.setFont(mono(7))
    sub.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
    mid.addWidget(sub)
    lay.addLayout(mid)
    lay.addStretch()

    right_col = QVBoxLayout()
    right_col.setSpacing(2)
    clock = QLabel("00:00:00")
    clock.setFont(mono(14, True))
    clock.setStyleSheet(f"color: {C.PRI}; background: transparent;")
    clock.setAlignment(Qt.AlignmentFlag.AlignRight)
    right_col.addWidget(clock)
    date = QLabel("")
    date.setFont(mono(7))
    date.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
    date.setAlignment(Qt.AlignmentFlag.AlignRight)
    right_col.addWidget(date)
    lay.addLayout(right_col)

    # Top bar montado. Banner amber va debajo (oculto por default).
    outer.addWidget(top)

    # Banner amber para advertencias como vision_threshold_reached
    # (issue ggml-org/llama.cpp#21690). Oculto por default; main_window
    # lo muestra cuando recibe el evento del BUS via EventBusBridge.
    vision_banner = QPushButton("")
    vision_banner.setFont(mono(7, True))
    vision_banner.setVisible(False)
    vision_banner.setCursor(Qt.CursorShape.PointingHandCursor)
    vision_banner.setStyleSheet(
        f"QPushButton {{ color: #0a0a0a; background: {C.ACC2}; "
        f"border: none; padding: 4px 10px; }} "
        f"QPushButton:hover {{ background: #ffd166; }}"
    )

    handles: dict[str, Any] = {
        "clock_lbl": clock, "date_lbl": date, "brand_lbl": left_brand,
        "vision_banner": vision_banner,
    }

    # Click en el banner -> ocultar (es informativo, no bloqueante)
    vision_banner.clicked.connect(lambda _=False: vision_banner.setVisible(False))
    outer.addWidget(vision_banner)

    def _tick() -> None:
        clock.setText(time.strftime("%H:%M:%S"))
        date.setText(time.strftime("%a %d %b %Y").upper())

    tmr = QTimer(w)
    tmr.timeout.connect(_tick)
    tmr.start(1000)
    _tick()
    handles["clock_timer"] = tmr
    return w, handles


# ---------------------------------------------------------------------------
def build_left_panel() -> tuple[QWidget, dict[str, Any]]:
    w = QWidget()
    w.setFixedWidth(_LEFT_W)
    w.setStyleSheet(f"background: {C.DARK}; border-right: 1px solid {C.BORDER};")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(10, 12, 10, 12)
    lay.setSpacing(6)

    # SYS MONITOR header
    h1 = QLabel("◈  SYS MONITOR")
    h1.setFont(mono(7, True))
    h1.setStyleSheet(
        f"color: {C.PRI}; background: transparent; "
        f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;"
    )
    lay.addWidget(h1)
    lay.addSpacing(2)

    bar_cpu  = MetricBar("CPU", C.PRI)
    bar_mem  = MetricBar("MEM", C.ACC2)
    bar_gpu  = MetricBar("GPU", C.ACC)
    bar_net  = MetricBar("NET", C.GREEN)
    bar_disk = MetricBar("DSK", C.TEXT_MED)
    bar_tmp  = MetricBar("TMP", "#ff6688")
    for bar in (bar_cpu, bar_mem, bar_gpu, bar_net, bar_disk, bar_tmp):
        lay.addWidget(bar)

    lay.addSpacing(4)

    # System info card
    info = QWidget()
    info.setStyleSheet(panel_qss())
    info_lay = QVBoxLayout(info)
    info_lay.setContentsMargins(8, 6, 8, 6)
    info_lay.setSpacing(3)

    uptime = QLabel("UP  --:--")
    uptime.setFont(mono(8, True))
    uptime.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
    info_lay.addWidget(uptime)

    procs = QLabel("PROC  --")
    procs.setFont(mono(8))
    procs.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
    info_lay.addWidget(procs)

    osl = QLabel(f"OS  {metrics_mod.os_short()}")
    osl.setFont(mono(8))
    osl.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
    info_lay.addWidget(osl)

    lay.addWidget(info)
    lay.addSpacing(6)

    # Context budget bar (K3)
    ctx_label = QLabel("▸ CONTEXT BUDGET")
    ctx_label.setFont(mono(7, True))
    ctx_label.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
    lay.addWidget(ctx_label)

    budget_bar = MetricBar("CTX", C.PRI)
    lay.addWidget(budget_bar)

    # Fase V — Profile selector
    prof_label = QLabel("▸ VRAM PROFILE")
    prof_label.setFont(mono(7, True))
    prof_label.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
    lay.addWidget(prof_label)

    prof_row = QHBoxLayout()
    prof_row.setContentsMargins(0, 0, 0, 0)
    prof_row.setSpacing(2)
    prof_buttons: dict[str, QPushButton] = {}
    # 2026-05-26: sistema colapsado a un solo perfil (vram4 = E2B-Q4, ≤4 GB) +
    # standby (server off). Antes había 5 chips por VRAM; ahora sólo VRAM4 y
    # STANDBY. Los nombres legacy igual resuelven a vram4 vía _resolve_alias.
    for code, full in (("VRAM4", "vram4"), ("STDBY", "standby")):
        btn = QPushButton(code)
        btn.setFont(mono(6, True))
        btn.setFixedHeight(20)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("profile_name", full)
        btn.setProperty("active", False)
        # styling es manejado por main_window cuando cambia el activo
        btn.setStyleSheet(
            f"QPushButton {{ background: {C.PANEL2}; color: {C.TEXT_DIM}; "
            f"border: 1px solid {C.BORDER}; border-radius: 2px; padding: 2px; }}"
            f"QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_A}; }}"
        )
        prof_row.addWidget(btn, stretch=1)
        prof_buttons[full] = btn
    prof_wrap = QWidget(); prof_wrap.setLayout(prof_row)
    lay.addWidget(prof_wrap)

    lay.addStretch()

    # Status badges
    badges_data = [
        ("AI CORE\nACTIVE", C.GREEN, "core"),
        ("SEC\nCLEARED",   C.PRI,   "sec"),
        ("PROTOCOL\nMARK I", C.TEXT_DIM, "protocol"),
    ]
    badges: dict[str, QLabel] = {}
    for txt, col, key in badges_data:
        lbl = QLabel(txt)
        lbl.setFont(mono(7, True))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {col}; background: {C.PANEL2}; "
            f"border: 1px solid {C.BORDER_A}; border-radius: 3px; padding: 4px;"
        )
        lay.addWidget(lbl)
        badges[key] = lbl

    handles: dict[str, Any] = {
        "bar_cpu": bar_cpu, "bar_mem": bar_mem, "bar_gpu": bar_gpu,
        "bar_net": bar_net, "bar_disk": bar_disk, "bar_tmp": bar_tmp,
        "uptime_lbl": uptime, "procs_lbl": procs, "os_lbl": osl,
        "budget_bar": budget_bar, "badges": badges,
        "profile_buttons": prof_buttons,
    }
    return w, handles


# ---------------------------------------------------------------------------
def build_right_panel(
    *,
    log_widget: QWidget,
    on_send: Callable[[str], None],
    on_open_sessions: Callable[[], None],
    on_open_settings: Callable[[], None],
    on_open_triggers: Callable[[], None],
    on_open_memory: Callable[[], None],
    on_open_tools: Callable[[], None],
    on_attach_image: Callable[[], None],
) -> tuple[QWidget, dict[str, Any]]:
    w = QWidget()
    w.setFixedWidth(_RIGHT_W)
    w.setStyleSheet(f"background: {C.DARK}; border-left: 1px solid {C.BORDER};")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(10, 10, 10, 10)
    lay.setSpacing(6)

    def _sec(txt: str) -> QLabel:
        l = QLabel(f"▸ {txt}")
        l.setFont(mono(7, True))
        l.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        return l

    lay.addWidget(_sec("ACTIVITY LOG"))
    lay.addWidget(log_widget, stretch=1)

    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
    lay.addWidget(sep)

    # Action button strip
    actions_row1 = QHBoxLayout()
    actions_row1.setSpacing(4)
    btns_def = [
        ("⊞  SESSIONS",  on_open_sessions),
        ("⚙  SETTINGS",  on_open_settings),
    ]
    for label, cb in btns_def:
        b = QPushButton(label)
        b.setFont(mono(7, True))
        b.setFixedHeight(26)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(button_qss(primary=True))
        b.clicked.connect(cb)
        actions_row1.addWidget(b)
    lay.addLayout(actions_row1)

    actions_row2 = QHBoxLayout()
    actions_row2.setSpacing(4)
    btns2 = [
        ("✦  TRIGGERS",  on_open_triggers),
        ("✜  MEMORY",    on_open_memory),
        ("☷  TOOLS",     on_open_tools),
    ]
    for label, cb in btns2:
        b = QPushButton(label)
        b.setFont(mono(7))
        b.setFixedHeight(24)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(button_qss())
        b.clicked.connect(cb)
        actions_row2.addWidget(b)
    lay.addLayout(actions_row2)

    lay.addSpacing(4)
    lay.addWidget(_sec("COMMAND INPUT"))

    input_row = QHBoxLayout()
    input_row.setSpacing(5)

    inp = QLineEdit()
    inp.setPlaceholderText("Talk to GEMMA4... ")
    inp.setFont(mono(10))
    inp.setFixedHeight(34)
    inp.setStyleSheet(line_edit_qss())
    input_row.addWidget(inp)

    attach = QPushButton("📎")
    attach.setFixedSize(34, 34)
    attach.setToolTip("Attach image")
    attach.setCursor(Qt.CursorShape.PointingHandCursor)
    attach.setStyleSheet(button_qss())
    attach.clicked.connect(on_attach_image)
    input_row.addWidget(attach)

    send = QPushButton("▸")
    send.setFixedSize(38, 34)
    send.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
    send.setCursor(Qt.CursorShape.PointingHandCursor)
    send.setStyleSheet(button_qss(primary=True))
    input_row.addWidget(send)

    lay.addLayout(input_row)

    def _do_send() -> None:
        text = inp.text().strip()
        if not text:
            return
        inp.clear()
        on_send(text)

    send.clicked.connect(_do_send)
    inp.returnPressed.connect(_do_send)

    # Attachment hint
    hint = QLabel("No attachments")
    hint.setFont(mono(7))
    hint.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
    hint.setWordWrap(True)
    lay.addWidget(hint)

    handles: dict[str, Any] = {
        "input": inp,
        "send_btn": send,
        "attach_btn": attach,
        "attach_hint": hint,
    }
    return w, handles


# ---------------------------------------------------------------------------
def build_footer() -> tuple[QWidget, dict[str, Any]]:
    w = QWidget()
    w.setFixedHeight(24)
    w.setStyleSheet(f"background: {C.DARK}; border-top: 1px solid {C.BORDER};")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(14, 0, 14, 0)

    def _fl(txt: str, color: str = C.TEXT_MED) -> QLabel:
        l = QLabel(txt)
        l.setFont(mono(7))
        l.setStyleSheet(f"color: {color}; background: transparent;")
        return l

    sc = _fl("[F11] FS  ·  [Ctrl+L] Clear  ·  [Ctrl+N] New  ·  [Ctrl+,] Settings")
    lay.addWidget(sc)
    lay.addStretch()
    mid = _fl("LOCAL.AI  ·  GEMMA4-MARK-I  ·  CLASSIFIED")
    lay.addWidget(mid)
    lay.addStretch()
    sess = _fl("session: --", C.PRI_DIM)
    lay.addWidget(sess)
    footer_handles: dict[str, Any] = {"sess_lbl": sess, "shortcut_lbl": sc, "mid_lbl": mid}
    return w, footer_handles
