"""EXPERIMENTO (sin enviar): nailear el mecanismo correcto para abrir un GRUPO por el
BUSCADOR PRINCIPAL de WhatsApp (no Ctrl+N). Maximiza WhatsApp (UI grande=OCR-friendly),
OCR-find 'Buscar' -> click, tipea 'Letras', Down+Enter, y OCR del encabezado para
confirmar que abrió el grupo Letras. Screenshots en cada paso para LEER."""
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

def focus_max(h):
    fg = u32.GetForegroundWindow()
    t1 = win32process.GetWindowThreadProcessId(fg)[0]; t2 = win32process.GetWindowThreadProcessId(h)[0]
    if t1 != t2: u32.AttachThreadInput(t1, t2, True)
    win32gui.ShowWindow(h, win32con.SW_MAXIMIZE); win32gui.SetForegroundWindow(h)
    if t1 != t2: u32.AttachThreadInput(t1, t2, False)
    time.sleep(0.8)

# elegir la ventana WhatsApp VISIBLE (rect on-screen, no la minimizada -32000)
wins = [(h, r) for h, r in find_wa() if r[0] > -10000]
if not wins:
    # forzar restore de cualquiera
    wins = find_wa()
h, _ = wins[0]
focus_max(h)
rect = win32gui.GetWindowRect(h)
L, T, R, B = rect; W, H = R - L, B - T
print(f"[wa] rect={rect}", flush=True)

def shot(name):
    p = (OUT / f"ms_{name}.png").resolve(); ImageGrab.grab().convert("RGB").save(str(p)); return p

def click(x, y):
    ex("gui", {"action": "click", "x": int(x), "y": int(y)})

p0 = shot("0_before")
# 1) localizar el buscador principal por OCR ('Buscar' arriba-izquierda)
f = ocr_find_text(p0, "Buscar")
cands = [m for m in (f.get("matches", []) if f.get("ok") else [])
         if m["center_x"] < L + W * 0.32 and m["center_y"] < T + H * 0.18]
if cands:
    sb = cands[0]; sx, sy = sb["center_x"], sb["center_y"]
    print(f"[search] 'Buscar' en ({sx},{sy})", flush=True)
else:
    sx, sy = int(L + W * 0.12), int(T + H * 0.095)
    print(f"[search] OCR no halló 'Buscar'; fallback ({sx},{sy})", flush=True)
click(sx, sy); time.sleep(0.5)
ex("gui", {"action": "keypress", "keys": "ctrl+a", "window": "WhatsApp", "method": "sendkeys"}); time.sleep(0.2)
ex("gui", {"action": "type", "text": "Letras", "window": "WhatsApp", "method": "sendkeys"}); time.sleep(1.3)
shot("1_typed_letras")
# 2) seleccionar el primer resultado: Down + Enter
ex("gui", {"action": "keypress", "keys": "down", "window": "WhatsApp", "method": "sendkeys"}); time.sleep(0.4)
ex("gui", {"action": "keypress", "keys": "enter", "window": "WhatsApp", "method": "sendkeys"}); time.sleep(1.0)
p2 = shot("2_opened")
# 3) OCR del ENCABEZADO (banda superior del área de chat, a la derecha del sidebar)
hdr = (OUT / "ms_header_crop.png").resolve()
img = ImageGrab.grab().convert("RGB")
crop = img.crop((int(L + W * 0.33), int(T + H * 0.02), int(L + W * 0.80), int(T + H * 0.12)))
crop.save(str(hdr))
fh = ocr_find_text(hdr, "Letras")
print(f"[header] OCR-find 'Letras' en el encabezado: found={fh.get('found')} ocr_text={fh.get('ocr_text','')[:80]!r}", flush=True)
print("[done] screenshots ms_*.png — NADA enviado", flush=True)
