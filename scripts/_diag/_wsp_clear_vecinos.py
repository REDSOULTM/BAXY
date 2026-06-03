"""Limpia el draft que el BUG VIEJO dejó en 'Vecinos Alto Caucamá' (mi msg de prueba).
Busca el grupo por el buscador principal, VERIFICA el encabezado 'Vecinos' por región
(no tocar el chat equivocado), y SOLO ahí Ctrl+A+Delete el compose. NO envía."""
from __future__ import annotations
import os, sys, time, ctypes
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)
import win32gui, win32process, win32con
from PIL import ImageGrab
from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.tools_pkg.ops_tools import ocr_find_text

OUT = Path("scripts/_diag/_wsp"); OUT.mkdir(parents=True, exist_ok=True)
u32 = ctypes.windll.user32
a = Gemma4Agent(); ex = a.tools.execute
def find_wa():
    res = []
    def cb(h, _):
        if win32gui.IsWindowVisible(h) and "whatsapp" in (win32gui.GetWindowText(h) or "").lower():
            res.append((h, win32gui.GetWindowRect(h)))
        return True
    win32gui.EnumWindows(cb, None); return res
h = ([(h, r) for h, r in find_wa() if r[0] > -10000] or find_wa())[0][0]
fg = u32.GetForegroundWindow()
t1 = win32process.GetWindowThreadProcessId(fg)[0]; t2 = win32process.GetWindowThreadProcessId(h)[0]
if t1 != t2: u32.AttachThreadInput(t1, t2, True)
win32gui.ShowWindow(h, win32con.SW_MAXIMIZE); win32gui.SetForegroundWindow(h)
if t1 != t2: u32.AttachThreadInput(t1, t2, False)
time.sleep(0.8)
L, T, Rr, Bb = win32gui.GetWindowRect(h); W, Hh = Rr - L, Bb - T

def shot(n):
    p = (OUT / f"vec_{n}.png").resolve(); ImageGrab.grab().convert("RGB").save(str(p)); return p
p0 = shot("0")
f = ocr_find_text(p0, "Buscar")
cand = next(((m["center_x"], m["center_y"]) for m in (f.get("matches", []) if f.get("ok") else [])
             if m["center_x"] < L + W * 0.32 and m["center_y"] < T + Hh * 0.20),
            (int(L + W * 0.12), int(T + Hh * 0.095)))
ex("gui", {"action": "click", "x": int(cand[0]), "y": int(cand[1])}); time.sleep(0.5)
ex("gui", {"action": "keypress", "keys": "ctrl+a", "window": "WhatsApp", "method": "sendkeys"}); time.sleep(0.2)
ex("gui", {"action": "type", "text": "Vecinos Alto", "window": "WhatsApp", "method": "sendkeys"}); time.sleep(1.3)
ex("gui", {"action": "keypress", "keys": "down", "window": "WhatsApp", "method": "sendkeys"}); time.sleep(0.4)
ex("gui", {"action": "keypress", "keys": "enter", "window": "WhatsApp", "method": "sendkeys"}); time.sleep(1.0)
# verificar encabezado 'Vecinos'
pv = shot("opened")
fv = ocr_find_text(pv, "Vecinos", min_conf=20)
hx0, hx1, hy0, hy1 = L + W * 0.30, L + W * 0.88, T + Hh * 0.02, T + Hh * 0.18
ok = any(hx0 <= m["center_x"] <= hx1 and hy0 <= m["center_y"] <= hy1
         for m in (fv.get("matches", []) if fv.get("found") else []))
print(f"[verify] 'Vecinos' en encabezado: {ok}", flush=True)
if not ok:
    print("[ABORT] no confirmé Vecinos -> NO borro nada.", flush=True); sys.exit(0)
# click compose + Ctrl+A + Delete
cx = int(L + W * 0.62); cy = int(Bb - 38)
u32.SetCursorPos(cx, cy); u32.mouse_event(0x0002, 0, 0, 0, 0); u32.mouse_event(0x0004, 0, 0, 0, 0); time.sleep(0.3)
ex("gui", {"action": "keypress", "keys": "ctrl+a", "window": "WhatsApp", "method": "sendkeys"}); time.sleep(0.2)
for _ in range(3):
    u32.keybd_event(0x2E, 0, 0, 0); u32.keybd_event(0x2E, 0, 2, 0); time.sleep(0.05)  # Delete
shot("cleared")
print("[done] draft de Vecinos limpiado (Ctrl+A+Delete). LEER vec_cleared.png", flush=True)
