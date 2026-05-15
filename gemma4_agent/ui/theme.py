"""Theme tokens for the Jarvis-style GUI.

Palette inspired by Mark XXXIX. Cyan/turquoise on near-black blue, orange and
amber accents, alert red, success green. Mono fonts for HUD text, body font
for chat content.

Every color is a hex string. Use `qcol(C.PRI, alpha)` to get a QColor.
"""
from __future__ import annotations

from PyQt6.QtGui import QColor, QFont


class C:
    """Named color palette. Modifying these re-skins the whole UI."""

    # Backgrounds
    BG          = "#00060a"   # deepest — root canvas
    PANEL       = "#010d14"   # panel surfaces
    PANEL2      = "#010f18"   # raised panel (info cards)
    DARK        = "#000d14"   # header/footer chrome
    BAR_BG      = "#011520"   # progress bar trough
    OVERLAY     = "#000810f0" # modal dim overlay

    # Borders
    BORDER      = "#0d3347"
    BORDER_B    = "#1a5c7a"   # hover/active
    BORDER_A    = "#0f4060"   # accent

    # Primary cyan
    PRI         = "#00d4ff"   # iconic Jarvis cyan
    PRI_DIM     = "#007a99"
    PRI_GHO     = "#001f2e"

    # Accents
    ACC         = "#ff6b00"   # orange — secondary scanners
    ACC2        = "#ffcc00"   # amber — warnings / thinking

    # Status semantics
    GREEN       = "#00ff88"
    GREEN_D     = "#00aa55"
    RED         = "#ff3355"
    MUTED_C     = "#ff3366"
    PURPLE      = "#a855f7"   # listening (voice future)

    # Text
    TEXT        = "#8ffcff"   # primary readable on dark
    TEXT_DIM    = "#3a8a9a"
    TEXT_MED    = "#5ab8cc"
    WHITE       = "#d8f8ff"

    # Tool roles
    TOOL_OK     = "#00ff88"
    TOOL_FAIL   = "#ff3355"
    TOOL_RUN    = "#ffcc00"
    TOOL_NAME   = "#00d4ff"


# State -> (label, color, blink-symbols)
# Symbols use BMP unicode that ships in Windows' Segoe UI Symbol font and most
# Linux/macOS monospace stacks. The HUD selects `symbol_font()` for these.
STATE_TABLE: dict[str, tuple[str, str, tuple[str, str]]] = {
    "INITIALISING": ("INITIALISING",  C.ACC2,    ("◈", "◇")),  # diamonds
    "IDLE":         ("STANDBY",       C.PRI,     ("●", "○")),  # filled/empty circle
    "LISTENING":    ("LISTENING",     C.GREEN,   ("●", "○")),
    "THINKING":     ("THINKING",      C.ACC2,    ("◈", "◇")),
    "PROCESSING":   ("PROCESSING",    C.ACC2,    ("▷", "▶")),  # open/filled right triangle
    "EXECUTING":    ("EXECUTING",     C.PRI,     ("▸", "▹")),
    "SPEAKING":     ("SPEAKING",      C.ACC,     ("●", "●")),
    "ERROR":        ("ERROR",         C.RED,     ("⊘", "⊘")),  # circled slash
    "MUTED":        ("MUTED",         C.MUTED_C, ("⊘", "⊘")),
    "OFFLINE":      ("OFFLINE",       C.RED,     ("⊘", "⊘")),
}


def qcol(hex_str: str, alpha: int = 255) -> QColor:
    """Build a QColor from a #rrggbb string with optional alpha 0-255."""
    c = QColor(hex_str)
    c.setAlpha(alpha)
    return c


def mono(size: int = 9, bold: bool = False) -> QFont:
    """Monospace font for HUD text and logs."""
    f = QFont("Courier New", size)
    f.setBold(bold)
    return f


def display(size: int = 14, bold: bool = True) -> QFont:
    """Big display font for header titles."""
    f = QFont("Courier New", size)
    f.setBold(bold)
    f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 110)
    return f


def body(size: int = 10, bold: bool = False) -> QFont:
    """Body text font for chat content."""
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    return f


def symbol_font(size: int = 11, bold: bool = True) -> QFont:
    """Font that reliably renders BMP symbols like ◈ ● ▷ ⊘.

    On Windows, Segoe UI Symbol ships by default. On Linux/macOS, DejaVu Sans
    Mono or system mono covers the same range. QFont falls back automatically
    if the requested family is missing.
    """
    families = ["Segoe UI Symbol", "DejaVu Sans Mono", "Consolas", "Courier New"]
    f = QFont(families[0], size)
    f.setFamilies(families)
    f.setBold(bold)
    return f


# Reusable QSS snippets
def line_edit_qss() -> str:
    return f"""
        QLineEdit {{
            background: #000d14;
            color: {C.WHITE};
            border: 1px solid {C.BORDER};
            border-radius: 3px;
            padding: 4px 8px;
            selection-background-color: {C.PRI_GHO};
        }}
        QLineEdit:focus {{
            border: 1px solid {C.PRI};
        }}
    """


def text_edit_qss() -> str:
    return f"""
        QTextEdit, QPlainTextEdit {{
            background: {C.PANEL};
            color: {C.TEXT};
            border: 1px solid {C.BORDER};
            border-radius: 4px;
            padding: 6px;
            selection-background-color: {C.PRI_GHO};
        }}
        QScrollBar:vertical {{
            background: {C.BG};
            width: 8px;
            border: none;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {C.BORDER_B};
            border-radius: 4px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {C.PRI_DIM};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
            border: none;
            background: none;
        }}
    """


def button_qss(*, primary: bool = False, danger: bool = False) -> str:
    if danger:
        fg, border = C.RED, C.RED
        bg = "#140006"
    elif primary:
        fg, border = C.PRI, C.PRI_DIM
        bg = "transparent"
    else:
        fg, border = C.TEXT_MED, C.BORDER
        bg = "transparent"
    return f"""
        QPushButton {{
            background: {bg};
            color: {fg};
            border: 1px solid {border};
            border-radius: 3px;
            padding: 4px 12px;
        }}
        QPushButton:hover {{
            background: {C.PRI_GHO};
            color: {C.PRI};
            border: 1px solid {C.PRI};
        }}
        QPushButton:disabled {{
            color: {C.TEXT_DIM};
            border: 1px solid {C.BORDER_A};
        }}
    """


def panel_qss() -> str:
    return f"""
        background: {C.PANEL2};
        border: 1px solid {C.BORDER_A};
        border-radius: 4px;
    """


def combo_qss() -> str:
    return f"""
        QComboBox {{
            background: #000d14;
            color: {C.TEXT};
            border: 1px solid {C.BORDER};
            border-radius: 3px;
            padding: 4px 8px;
        }}
        QComboBox:hover {{
            border: 1px solid {C.BORDER_B};
        }}
        QComboBox QAbstractItemView {{
            background: {C.PANEL};
            color: {C.TEXT};
            selection-background-color: {C.PRI_GHO};
            border: 1px solid {C.BORDER_B};
        }}
        QComboBox::drop-down {{
            border: none;
        }}
    """
