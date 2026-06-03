"""Limpia el draft que quedó en el chat EQUIVOCADO (Vecinos Alto Caucamá) por el bug
del tool (Ctrl+N no halla grupos -> tipeó en el chat abierto). Enfoca WhatsApp, clickea
la caja de redacción, selecciona todo y borra. NO envía. Screenshot para confirmar."""
from __future__ import annotations
import sys, time, ctypes
from pathlib import Path
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
import win32gui, win32process, win32con
from PIL import ImageGrab

OUT = Path("scripts/_diag/_wsp"); OUT.mkdir(parents=True, exist_ok=True)
u32 = ctypes.windll.user32

def find_wa():
    res = []
    def cb(h, _):
        if win32gui.IsWindowVisible(h) and "whatsapp" in win32gui.GetWindowText(h).lower():
            res.append((h, win32gui.GetWindowRect(h)))
        return True
    win32gui.EnumWindows(cb, None); return res

wa = find_wa()
if not wa:
    print("[ABORT] no encontré WhatsApp"); sys.exit(1)
h, rect = wa[0]
l, t, r, b = rect
print(f"[wa] rect={rect}", flush=True)

# focus robusto
fg = u32.GetForegroundWindow()
t1 = win32process.GetWindowThreadProcessId(fg)[0]; t2 = win32process.GetWindowThreadProcessId(h)[0]
if t1 != t2: u32.AttachThreadInput(t1, t2, True)
win32gui.ShowWindow(h, win32con.SW_RESTORE); win32gui.SetForegroundWindow(h)
if t1 != t2: u32.AttachThreadInput(t1, t2, False)
time.sleep(0.7)

def key(vk, *mods):
    for m in mods: u32.keybd_event(m, 0, 0, 0)
    u32.keybd_event(vk, 0, 0, 0); u32.keybd_event(vk, 0, 2, 0)
    for m in reversed(mods): u32.keybd_event(m, 0, 2, 0)

# 1) Escape: cierra el panel "Nuevo chat" -> vuelve al chat (Vecinos) con su compose
key(0x1B); time.sleep(0.4)
# 2) click en la caja de redacción (abajo, área de chat = a la derecha del panel izq)
cx = int(l + (r - l) * 0.62); cy = int(b - 38)
u32.SetCursorPos(cx, cy); u32.mouse_event(0x0002, 0, 0, 0, 0); u32.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(0.4)
# 3) seleccionar todo (Ctrl+A) y borrar
key(0x41, 0x11); time.sleep(0.2)   # Ctrl+A
key(0x2E); time.sleep(0.2)         # Delete
key(0x08); time.sleep(0.3)         # Backspace (por si Delete no alcanzó)
ImageGrab.grab().convert("RGB").save(str((OUT / "cleared.png").resolve()))
print(f"[click-compose] ({cx},{cy})  -> Ctrl+A + Delete/Backspace", flush=True)
print("[screenshot] scripts/_diag/_wsp/cleared.png (LEER: caja vacía, NADA enviado)", flush=True)
print("[done]", flush=True)
