"""HUD canvas — the centerpiece of the GUI.

A circular Jarvis-style head-up display with:
  - 3 concentric arc rings spinning at different speeds
  - radial halo pulsing per state
  - 2 scanner arcs cruising at different rotations
  - radial tick marks every 10 degrees (longer every 30)
  - corner brackets framing the disc
  - central crosshair
  - particle emitter (radial) active in SPEAKING/THINKING
  - waveform bar at the base (35 bars, randomized in speaking)
  - status text with blinking symbol
  - pulse rings emitted from center (expanding outward, fading)
  - background dot grid

Runs at ~60fps via QTimer(16ms).
"""
from __future__ import annotations

import math
import random
import time

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap, QRadialGradient
from PyQt6.QtWidgets import QSizePolicy, QWidget

from .theme import C, STATE_TABLE, qcol, symbol_font


class HudCanvas(QWidget):
    """The central animated HUD widget."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # state ---------------------------------------------------------
        self.state: str = "INITIALISING"
        self.muted: bool = False
        self.connected: bool = False
        self.assistant_name: str = "GEMMA4"
        self.persona_name: str = "default"
        self.model_name: str = "gemma-3n-e4b-it"

        # animation state ----------------------------------------------
        self._tick = 0
        self._scale = 1.0
        self._target_scale = 1.0
        self._halo = 55.0
        self._target_halo = 55.0
        self._last_target_t = time.time()

        # rings (independent rotations + speeds)
        self._rings = [0.0, 120.0, 240.0]
        self._scan = 0.0
        self._scan2 = 180.0
        self._pulses: list[float] = [0.0, 60.0, 130.0]
        self._particles: list[list[float]] = []
        self._blink = True
        self._blink_tick = 0
        self._face: QPixmap | None = None

        # waveform sequence cache (smooth idle wave)
        self._wave_phase = 0.0

        # background grid scroll
        self._grid_off = 0.0

        # timer @ 60 fps
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(16)

    # ------------------------------------------------------------------
    def set_face(self, pixmap: QPixmap | None) -> None:
        """Optional circular face/avatar drawn at the center."""
        self._face = pixmap
        self.update()

    def set_state(self, new_state: str) -> None:
        if new_state in STATE_TABLE or new_state in {"INITIALISING", "OFFLINE"}:
            self.state = new_state
            self.update()

    def set_connected(self, ok: bool) -> None:
        self.connected = ok
        if not ok and self.state in {"IDLE", "LISTENING"}:
            self.state = "OFFLINE"
        self.update()

    def set_persona(self, name: str) -> None:
        self.persona_name = (name or "default")[:32]
        self.update()

    def set_model(self, name: str) -> None:
        self.model_name = (name or "")[:48]
        self.update()

    # ------------------------------------------------------------------
    def _speed_for_state(self) -> tuple[float, float, float, float, float]:
        """Returns (ring_speed_mult, scan_speed, scan2_speed, pulse_speed, particle_prob)."""
        if self.state == "SPEAKING":
            return 2.0, 3.0, -2.0, 4.5, 0.28
        if self.state in ("THINKING", "PROCESSING"):
            return 1.5, 2.2, -1.6, 3.2, 0.18
        if self.state == "EXECUTING":
            return 1.7, 2.6, -1.8, 3.6, 0.20
        if self.state == "LISTENING":
            return 1.1, 1.6, -1.2, 2.4, 0.08
        if self.state in ("ERROR", "MUTED", "OFFLINE"):
            return 0.3, 0.6, -0.4, 1.0, 0.0
        # IDLE / INITIALISING
        return 0.8, 1.3, -0.85, 2.0, 0.04

    def _target_for_state(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Returns ((scale_min,max), (halo_min,max))."""
        if self.state == "SPEAKING":
            return (1.06, 1.14), (155, 195)
        if self.state in ("THINKING", "PROCESSING"):
            return (1.02, 1.05), (110, 145)
        if self.state == "EXECUTING":
            return (1.03, 1.08), (130, 170)
        if self.state == "LISTENING":
            return (1.005, 1.015), (75, 95)
        if self.state in ("ERROR", "MUTED", "OFFLINE"):
            return (0.99, 1.01), (15, 35)
        return (1.001, 1.008), (48, 68)

    def _step(self) -> None:
        self._tick += 1
        now = time.time()

        speaking = self.state == "SPEAKING"
        retarget_period = 0.12 if speaking else 0.5
        if now - self._last_target_t > retarget_period:
            (s_lo, s_hi), (h_lo, h_hi) = self._target_for_state()
            self._target_scale = random.uniform(s_lo, s_hi)
            self._target_halo = random.uniform(h_lo, h_hi)
            self._last_target_t = now

        sp = 0.38 if speaking else 0.15
        self._scale += (self._target_scale - self._scale) * sp
        self._halo += (self._target_halo - self._halo) * sp

        ring_mul, scan_sp, scan2_sp, pulse_sp, p_prob = self._speed_for_state()

        # rings
        self._rings[0] = (self._rings[0] + 0.55 * ring_mul) % 360
        self._rings[1] = (self._rings[1] - 0.35 * ring_mul) % 360
        self._rings[2] = (self._rings[2] + 0.90 * ring_mul) % 360

        # scanners
        self._scan = (self._scan + scan_sp) % 360
        self._scan2 = (self._scan2 + scan2_sp) % 360

        # pulses
        fw = min(self.width(), self.height())
        lim = fw * 0.78
        self._pulses = [r + pulse_sp for r in self._pulses if r + pulse_sp < lim]
        if len(self._pulses) < 3 and random.random() < (0.07 if speaking else 0.025):
            self._pulses.append(0.0)

        # particles
        if p_prob > 0 and random.random() < p_prob:
            cx, cy = self.width() / 2, self.height() / 2
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * 0.28
            speed = random.uniform(0.9, 2.4)
            self._particles.append([
                cx + math.cos(ang) * r_s, cy + math.sin(ang) * r_s,
                math.cos(ang) * speed,
                math.sin(ang) * speed - 0.4,
                1.0,
            ])
        self._particles = [
            [p[0] + p[2], p[1] + p[3], p[2] * 0.97, p[3] * 0.97, p[4] - 0.028]
            for p in self._particles
            if p[4] > 0
        ]
        # cap particles to avoid runaway
        if len(self._particles) > 220:
            self._particles = self._particles[-220:]

        # blink + idle wave
        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
        self._wave_phase += 0.09
        self._grid_off = (self._grid_off + 0.15) % 48

        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, a0: object) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))

        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)
        primary = self._state_color()

        # Cyan is the base color for "the suit"; primary tints halo/pulses/status only.
        base = C.PRI

        self._paint_grid(p, W, H)
        self._paint_corner_brackets(p, cx, cy, fw, base)
        self._paint_pulses(p, cx, cy, fw, primary)
        self._paint_halo(p, cx, cy, fw, primary)
        self._paint_spinning_rings(p, cx, cy, fw, base)
        self._paint_scanners(p, cx, cy, fw, primary)
        self._paint_tick_marks(p, cx, cy, fw, base)
        self._paint_crosshair(p, cx, cy, fw, base)
        self._paint_data_arc_labels(p, cx, cy, fw, base)
        self._paint_center_face(p, cx, cy, fw, base)
        self._paint_particles(p, primary)
        self._paint_hex_telemetry(p, cx, cy, fw, base)
        self._paint_status_text(p, cx, cy, fw, primary)
        self._paint_waveform(p, cx, cy, fw, primary)
        self._paint_metadata_strip(p, cx, cy, fw, base)

    def _state_color(self) -> str:
        if self.state in STATE_TABLE:
            return STATE_TABLE[self.state][1]
        return C.PRI

    # background dot grid scrolling slowly
    def _paint_grid(self, p: QPainter, W: int, H: int) -> None:
        p.setPen(QPen(qcol(C.PRI_GHO), 1))
        step = 48
        off = int(self._grid_off)
        for x in range(-off, W, step):
            for y in range(-off, H, step):
                p.drawPoint(x, y)

    def _paint_corner_brackets(self, p: QPainter, cx: float, cy: float, fw: int, primary: str) -> None:
        bl = 28
        bc = qcol(primary, 210)
        hl, hr = cx - fw // 2 + 8, cx + fw // 2 - 8
        ht, hb = cy - fw // 2 + 8, cy + fw // 2 - 8
        p.setPen(QPen(bc, 2))
        for bx, by, dx, dy in [
            (hl, ht, 1, 1),
            (hr, ht, -1, 1),
            (hl, hb, 1, -1),
            (hr, hb, -1, -1),
        ]:
            p.drawLine(QPointF(bx, by), QPointF(bx + dx * bl, by))
            p.drawLine(QPointF(bx, by), QPointF(bx, by + dy * bl))

    def _paint_pulses(self, p: QPainter, cx: float, cy: float, fw: int, primary: str) -> None:
        for pr in self._pulses:
            a = max(0, int(230 * (1.0 - pr / (fw * 0.78))))
            col = qcol(primary, a)
            p.setPen(QPen(col, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - pr, cy - pr, pr * 2, pr * 2))

    def _paint_halo(self, p: QPainter, cx: float, cy: float, fw: int, primary: str) -> None:
        r_face = fw * 0.31
        # filled radial gradient halo
        grad = QRadialGradient(cx, cy, r_face * 1.7)
        c0 = QColor(primary)
        c0.setAlpha(int(min(255, self._halo * 0.7)))
        c1 = QColor(primary)
        c1.setAlpha(0)
        grad.setColorAt(0.45, c0)
        grad.setColorAt(1.0, c1)
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), r_face * 1.7, r_face * 1.7)
        # outline halo rings
        for i in range(10):
            r = r_face * (1.85 - i * 0.085)
            frc = 1.0 - i / 10
            a = max(0, min(255, int(self._halo * 0.08 * frc)))
            col = qcol(primary, a)
            p.setPen(QPen(col, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

    def _paint_spinning_rings(self, p: QPainter, cx: float, cy: float, fw: int, primary: str) -> None:
        ring_defs = [
            (0.48, 3, 115, 78),
            (0.40, 2, 78, 55),
            (0.32, 1, 56, 40),
        ]
        for idx, (r_frac, w_r, arc_l, gap) in enumerate(ring_defs):
            ring_r = fw * r_frac
            base = self._rings[idx]
            a_val = max(0, min(255, int(self._halo * (1.0 - idx * 0.18))))
            col = qcol(primary, a_val)
            p.setPen(QPen(col, w_r))
            p.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
            angle = base
            while angle < base + 360:
                p.drawArc(rect, int(angle * 16), int(arc_l * 16))
                angle += arc_l + gap

    def _paint_scanners(self, p: QPainter, cx: float, cy: float, fw: int, primary: str) -> None:
        sr = fw * 0.50
        sa = min(255, int(self._halo * 1.5))
        ex = 75 if self.state == "SPEAKING" else 44
        p.setPen(QPen(qcol(primary, sa), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        srect = QRectF(cx - sr, cy - sr, sr * 2, sr * 2)
        p.drawArc(srect, int(self._scan * 16), int(ex * 16))
        p.setPen(QPen(qcol(C.ACC, sa // 2), 1.5))
        p.drawArc(srect, int(self._scan2 * 16), int(ex * 16))

    def _paint_tick_marks(self, p: QPainter, cx: float, cy: float, fw: int, primary: str) -> None:
        t_out, t_in = fw * 0.497, fw * 0.474
        p.setPen(QPen(qcol(primary, 140), 1))
        for deg in range(0, 360, 10):
            rad = math.radians(deg)
            inn = t_in if deg % 30 == 0 else t_in + 6
            p.drawLine(
                QPointF(cx + t_out * math.cos(rad), cy - t_out * math.sin(rad)),
                QPointF(cx + inn * math.cos(rad), cy - inn * math.sin(rad)),
            )
        # major-deg numerical labels every 30 deg
        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol(C.TEXT_DIM, 180), 1))
        for deg in (0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330):
            rad = math.radians(deg)
            lx = cx + (t_in - 14) * math.cos(rad)
            ly = cy - (t_in - 14) * math.sin(rad)
            p.drawText(QRectF(lx - 12, ly - 6, 24, 12),
                       Qt.AlignmentFlag.AlignCenter, f"{deg:03d}")

    def _paint_crosshair(self, p: QPainter, cx: float, cy: float, fw: int, primary: str) -> None:
        ch_r, gap_h = fw * 0.51, fw * 0.16
        p.setPen(QPen(qcol(primary, int(self._halo * 0.5)), 1))
        p.drawLine(QPointF(cx - ch_r, cy), QPointF(cx - gap_h, cy))
        p.drawLine(QPointF(cx + gap_h, cy), QPointF(cx + ch_r, cy))
        p.drawLine(QPointF(cx, cy - ch_r), QPointF(cx, cy - gap_h))
        p.drawLine(QPointF(cx, cy + gap_h), QPointF(cx, cy + ch_r))

    def _paint_data_arc_labels(self, p: QPainter, cx: float, cy: float, fw: int, primary: str) -> None:
        """Hex-like data tokens sliding along the outer ring."""
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(primary, 150), 1))
        tokens = ["0xA1F2", "0x40FF", "0x0CBE", "0xF003", "STARK", "MK-I", "SYS-OK", "00.AI"]
        r = fw * 0.55
        offset = (self._tick * 0.15) % 360
        per = 360 / len(tokens)
        for i, tok in enumerate(tokens):
            deg = i * per + offset
            rad = math.radians(deg)
            tx = cx + r * math.cos(rad) - 22
            ty = cy - r * math.sin(rad) - 6
            p.drawText(QRectF(tx, ty, 44, 12),
                       Qt.AlignmentFlag.AlignCenter, tok)

    def _paint_center_face(self, p: QPainter, cx: float, cy: float, fw: int, primary: str) -> None:
        if self._face is not None and not self._face.isNull():
            fsz = int(fw * 0.42 * self._scale)
            scaled = self._face.scaled(
                fsz, fsz,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(int(cx - fsz / 2), int(cy - fsz / 2), scaled)
            return

        # No face — paint orb
        orb_r = int(fw * 0.27 * self._scale)
        oc = QColor(primary)
        for i in range(12, 0, -1):
            r2 = int(orb_r * i / 12)
            frc = i / 12
            a = max(0, min(255, int(self._halo * 1.1 * frc)))
            cc = QColor(int(oc.red() * frc), int(oc.green() * frc), int(oc.blue() * frc), a)
            p.setBrush(QBrush(cc))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - r2, cy - r2, r2 * 2, r2 * 2))
        # iris ring (the bright inner ring of the orb)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(qcol(C.WHITE, 200), 1))
        ir = orb_r * 0.55
        p.drawEllipse(QRectF(cx - ir, cy - ir, ir * 2, ir * 2))
        # core highlight
        hl = orb_r * 0.22
        hg = QRadialGradient(cx - hl * 0.3, cy - hl * 0.3, hl * 1.4)
        hg.setColorAt(0.0, QColor(255, 255, 255, 220))
        hg.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx - hl * 0.3, cy - hl * 0.3), hl, hl)
        # name above orb
        p.setPen(QPen(qcol(primary, min(255, int(self._halo * 2))), 1))
        p.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        p.drawText(QRectF(cx - 110, cy + orb_r + 4, 220, 18),
                   Qt.AlignmentFlag.AlignCenter, self.assistant_name)

    def _paint_particles(self, p: QPainter, primary: str) -> None:
        for pt in self._particles:
            a = max(0, min(255, int(pt[4] * 255)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(primary, a)))
            p.drawEllipse(QPointF(pt[0], pt[1]), 2.5, 2.5)

    def _paint_hex_telemetry(self, p: QPainter, cx: float, cy: float, fw: int, primary: str) -> None:
        """Hex frame with telemetry labels around the orb (12 segments)."""
        r = fw * 0.43
        segments = [
            ("CPU", "OK"), ("MEM", "OK"), ("NET", "ON"), ("GPU", "STB"),
            ("LLM", "RDY"), ("MOD", "MK-I"), ("API", "L"), ("VEC", "OK"),
            ("KB", "FTS5"), ("MEM2", "PERS"), ("RT", f"{self._tick}"), ("STR", "EN"),
        ]
        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol(C.TEXT_DIM, 200), 1))
        for i, (k, v) in enumerate(segments):
            ang = math.radians(i * 30 + 15)
            tx = cx + r * math.cos(ang) - 22
            ty = cy - r * math.sin(ang) - 7
            p.drawText(QRectF(tx, ty, 44, 14), Qt.AlignmentFlag.AlignCenter, f"{k}·{v}")

    def _paint_metadata_strip(self, p: QPainter, cx: float, cy: float, fw: int, primary: str) -> None:
        """Strip near the top showing model + persona + connection status."""
        y = cy - fw * 0.46
        p.setFont(QFont("Consolas", 8))
        # left segment — model
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(cx - fw * 0.45, y, fw * 0.30, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"MOD  {self.model_name}")
        # center — persona
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(cx - fw * 0.12, y, fw * 0.24, 16),
                   Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter,
                   f"PERSONA · {self.persona_name.upper()}")
        # right — connection
        conn_col = C.GREEN if self.connected else C.RED
        p.setPen(QPen(qcol(conn_col), 1))
        p.drawText(QRectF(cx + fw * 0.20, y, fw * 0.25, 16),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   "● ONLINE" if self.connected else "○ OFFLINE")

    def _paint_status_text(self, p: QPainter, cx: float, cy: float, fw: int, primary: str) -> None:
        if self.state in STATE_TABLE:
            label, color, (sym_on, sym_off) = STATE_TABLE[self.state]
        else:
            label, color, (sym_on, sym_off) = (self.state, primary, ("●", "○"))
        sym = sym_on if self._blink else sym_off
        sy = cy + fw * 0.40
        p.setPen(QPen(qcol(color), 1))
        p.setFont(symbol_font(11, True))
        p.drawText(QRectF(0, sy, self.width(), 26),
                   Qt.AlignmentFlag.AlignCenter, f"{sym}  {label}")

    def _paint_waveform(self, p: QPainter, cx: float, cy: float, fw: int, primary: str) -> None:
        sy = cy + fw * 0.40 + 30
        N = 38
        bw = 8
        wx0 = (self.width() - N * bw) / 2
        for i in range(N):
            if self.state == "SPEAKING":
                hgt = random.randint(3, 22)
                cl = qcol(primary) if hgt > 12 else qcol(C.PRI_DIM)
            elif self.state in ("THINKING", "PROCESSING", "EXECUTING"):
                hgt = int(4 + 6 * abs(math.sin(self._wave_phase + i * 0.4)))
                cl = qcol(C.ACC2, 220)
            elif self.state == "LISTENING":
                hgt = int(3 + 4 * abs(math.sin(self._wave_phase * 1.5 + i * 0.7)))
                cl = qcol(C.GREEN)
            elif self.state in ("ERROR", "OFFLINE"):
                hgt = 2
                cl = qcol(C.RED)
            elif self.state == "MUTED":
                hgt = 2
                cl = qcol(C.MUTED_C)
            else:
                hgt = int(3 + 2 * math.sin(self._wave_phase * 0.6 + i * 0.6))
                cl = qcol(C.BORDER_B)
            p.fillRect(QRectF(wx0 + i * bw, sy + 22 - hgt, bw - 1, hgt), cl)
