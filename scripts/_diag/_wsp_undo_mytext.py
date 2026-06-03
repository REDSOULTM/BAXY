"""Quita EXACTAMENTE mi mensaje de prueba (que se agregó al draft del user en Letras),
por backspace de len(MSG) chars. Deja el draft del user ("que llego tardeque ya llego")
intacto. NO envía. Screenshot para confirmar."""
from __future__ import annotations
import sys, time, ctypes
from pathlib import Path
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
import win32gui, win32process, win32con
from PIL import ImageGrab

MSG = "Prueba automatica de Gemma 4 (asistente de voz) - envio a grupos OK - ignoren gracias"
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

n = len(MSG)
print(f"[undo] borrando {n} chars (mi mensaje) por backspace...", flush=True)
for _ in range(n):
    u32.keybd_event(0x08, 0, 0, 0); u32.keybd_event(0x08, 0, 2, 0)
    time.sleep(0.01)
time.sleep(0.4)
ImageGrab.grab().convert("RGB").save(str((OUT / "after_undo.png").resolve()))
print("[done] LEER after_undo.png — debe quedar SOLO tu draft 'que llego tardeque ya llego'", flush=True)
