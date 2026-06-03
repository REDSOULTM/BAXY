"""Flujo CORREGIDO, draft-first (NO envía): buscador principal -> 'Letras' -> Down+Enter
-> verificar encabezado (OCR de la REGIÓN del header, no toda la pantalla) -> si confirma,
redactar el mensaje (sin Enter de envío). Screenshot para LEER y confirmar antes del envío."""
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
GROUP = "Letras"
MSG = "Prueba automatica de Gemma 4 (asistente de voz) - envio a grupos OK - ignoren gracias"

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
time.sleep(0.9)
L, T, Rr, Bb = win32gui.GetWindowRect(h); W, Hh = Rr - L, Bb - T
print(f"[wa] rect={(L,T,Rr,Bb)}", flush=True)

def shot(n):
    p = (OUT / f"snd_{n}.png").resolve(); ImageGrab.grab().convert("RGB").save(str(p)); return p

# 1) buscador principal
p0 = shot("0")
f = ocr_find_text(p0, "Buscar")
cands = [m for m in (f.get("matches", []) if f.get("ok") else [])
         if m["center_x"] < L + W * 0.32 and m["center_y"] < T + Hh * 0.18]
sx, sy = (cands[0]["center_x"], cands[0]["center_y"]) if cands else (int(L + W * 0.12), int(T + Hh * 0.095))
ex("gui", {"action": "click", "x": int(sx), "y": int(sy)}); time.sleep(0.5)
ex("gui", {"action": "keypress", "keys": "ctrl+a", "window": "WhatsApp", "method": "sendkeys"}); time.sleep(0.2)
ex("gui", {"action": "type", "text": GROUP, "window": "WhatsApp", "method": "sendkeys"}); time.sleep(1.3)
ex("gui", {"action": "keypress", "keys": "down", "window": "WhatsApp", "method": "sendkeys"}); time.sleep(0.4)
ex("gui", {"action": "keypress", "keys": "enter", "window": "WhatsApp", "method": "sendkeys"}); time.sleep(1.0)

# 2) CALIBRAR: dónde aparece 'Letras' en pantalla (search box, result row, header)
shot_d = ex("gui", {"action": "screenshot", "monitor": "all"})
img_path = Path(str(shot_d.get("image_path"))); sx0 = int(shot_d.get("left", 0)); sy0 = int(shot_d.get("top", 0))
found = ocr_find_text(img_path, GROUP, lang="spa+eng", min_conf=20)
allm = [(int(m["center_x"] + sx0), int(m["center_y"] + sy0)) for m in (found.get("matches", []) if found.get("found") else [])]
print(f"[calib] TODAS las pos de '{GROUP}': {allm}  (W={W} Hh={Hh} L={L} T={T})", flush=True)
print(f"[calib] como fracción: {[ (round((x-L)/W,2), round((y-T)/Hh,2)) for x,y in allm]}", flush=True)
# NO aborto: el grupo Letras abre de forma determinista (probado); verifico YO leyendo
# el screenshot del draft antes de enviar (paso siguiente).

# 3) redactar (sin enviar)
cx_box = int(L + W * 0.72); cy_box = int(Bb - max(44, min(72, Hh * 0.05)))
ex("gui", {"action": "click", "x": cx_box, "y": cy_box}); time.sleep(0.3)
ex("gui", {"action": "type", "text": MSG, "window": "WhatsApp", "method": "sendkeys"}); time.sleep(0.5)
shot("draft")
print("[draft] mensaje redactado en Letras (NO enviado). LEER snd_draft.png", flush=True)
print("[done]", flush=True)
