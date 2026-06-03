"""ENVÍO REAL a Música (autorizado): re-verifica 'Música' en el encabezado JUSTO antes,
y si confirma, click compose + Enter (envía). Screenshot para confirmar el envío."""
from __future__ import annotations
import sys, time, ctypes
from pathlib import Path
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
import win32gui, win32process, win32con
from PIL import ImageGrab
from gemma4_agent.tools_pkg.ops_tools import ocr_find_text

OUT = Path("scripts/_diag/_wsp"); OUT.mkdir(parents=True, exist_ok=True)
u32 = ctypes.windll.user32
def find_wa():
    res = []
    def cb(h, _):
        if win32gui.IsWindowVisible(h) and "whatsapp" in (win32gui.GetWindowText(h) or "").lower():
            res.append((h, win32gui.GetWindowRect(h)))
        return True
    win32gui.EnumWindows(cb, None); return res
wins = [(h, r) for h, r in find_wa() if r[0] > -10000] or find_wa()
h = wins[0][0]
fg = u32.GetForegroundWindow()
t1 = win32process.GetWindowThreadProcessId(fg)[0]; t2 = win32process.GetWindowThreadProcessId(h)[0]
if t1 != t2: u32.AttachThreadInput(t1, t2, True)
win32gui.ShowWindow(h, win32con.SW_MAXIMIZE); win32gui.SetForegroundWindow(h)
if t1 != t2: u32.AttachThreadInput(t1, t2, False)
time.sleep(0.8)
L, T, Rr, Bb = win32gui.GetWindowRect(h); W, Hh = Rr - L, Bb - T

# re-verificar 'Música' en la región del encabezado
p = (OUT / "presend.png").resolve(); ImageGrab.grab().convert("RGB").save(str(p))
f = ocr_find_text(p, "Música", min_conf=20)
hx0, hx1 = L + W * 0.30, L + W * 0.88
hy0, hy1 = T + Hh * 0.02, T + Hh * 0.18
ok = any(hx0 <= m["center_x"] <= hx1 and hy0 <= m["center_y"] <= hy1
         for m in (f.get("matches", []) if f.get("found") else []))
print(f"[presend-verify] 'Música' en encabezado: {ok}", flush=True)
if not ok:
    print("[ABORT] no confirmé Música en el encabezado -> NO envío.", flush=True); sys.exit(0)

# click compose + Enter
cx = int(L + W * 0.62); cy = int(Bb - 38)
u32.SetCursorPos(cx, cy); u32.mouse_event(0x0002, 0, 0, 0, 0); u32.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(0.3)
u32.keybd_event(0x0D, 0, 0, 0); u32.keybd_event(0x0D, 0, 2, 0)  # Enter -> ENVÍA
time.sleep(1.0)
ImageGrab.grab().convert("RGB").save(str((OUT / "sent.png").resolve()))
print("[SENT] Enter enviado a Música. LEER sent.png (mensaje en el historial, compose vacío).", flush=True)
