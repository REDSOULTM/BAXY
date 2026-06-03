"""Explora la estructura UIA de WhatsApp Desktop (read-only): busca el cuadro de
búsqueda (Edit), el encabezado del chat, los ítems de la lista. Para diseñar un fix
robusto (buscar grupos + verificar encabezado por UIA, no por OCR de toda la pantalla).
Enfoca WhatsApp + screenshot + dump del árbol UIA."""
from __future__ import annotations
import sys, time, ctypes
from pathlib import Path
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
import win32gui, win32process, win32con
from PIL import ImageGrab
import uiautomation as auto

OUT = Path("scripts/_diag/_wsp"); OUT.mkdir(parents=True, exist_ok=True)
u32 = ctypes.windll.user32

def find_wa():
    res = []
    def cb(h, _):
        if win32gui.IsWindowVisible(h) and "whatsapp" in (win32gui.GetWindowText(h) or "").lower():
            res.append((h, win32gui.GetWindowRect(h)))
        return True
    win32gui.EnumWindows(cb, None); return res

wa = find_wa()
if not wa:
    print("[ABORT] no encontré WhatsApp"); sys.exit(1)
h, rect = wa[0]
print(f"[wa] rect={rect}", flush=True)
fg = u32.GetForegroundWindow()
t1 = win32process.GetWindowThreadProcessId(fg)[0]; t2 = win32process.GetWindowThreadProcessId(h)[0]
if t1 != t2: u32.AttachThreadInput(t1, t2, True)
win32gui.ShowWindow(h, win32con.SW_RESTORE); win32gui.SetForegroundWindow(h)
if t1 != t2: u32.AttachThreadInput(t1, t2, False)
time.sleep(0.8)
ImageGrab.grab().convert("RGB").save(str((OUT / "explore_state.png").resolve()))

try: auto.SetGlobalSearchTimeout(3.0)
except Exception: pass
root = auto.ControlFromHandle(h)
print(f"[root] {root.ControlTypeName} name={root.Name!r}", flush=True)

INTERESTING = {"EditControl", "ButtonControl", "ListControl", "ListItemControl",
               "TextControl", "DocumentControl", "GroupControl"}
count = [0]
def walk(ctrl, depth):
    if count[0] > 160 or depth > 9:
        return
    try:
        kids = ctrl.GetChildren()
    except Exception:
        return
    for k in kids:
        count[0] += 1
        if count[0] > 160:
            return
        try:
            tn = k.ControlTypeName; nm = (k.Name or "")[:45]; aid = k.AutomationId
            r = k.BoundingRectangle
            rr = (r.left, r.top, r.right, r.bottom) if r else None
        except Exception:
            tn, nm, aid, rr = "?", "", "", None
        if tn in INTERESTING and (nm or aid):
            print(f"  {'  '*depth}{tn:16} name={nm!r:47} aid={aid!r} rect={rr}", flush=True)
        walk(k, depth + 1)
walk(root, 0)
print("[done]", flush=True)
