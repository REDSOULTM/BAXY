"""Read-only: recorta + amplía la zona del compose box (y bordes) de WhatsApp para
leer EXACTAMENTE qué hay (¿draft previo del user + mi mensaje?). NO toca nada."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, ".")
import win32gui
from PIL import ImageGrab

OUT = Path("scripts/_diag/_wsp"); OUT.mkdir(parents=True, exist_ok=True)
def find_wa():
    res = []
    def cb(h, _):
        if win32gui.IsWindowVisible(h) and "whatsapp" in (win32gui.GetWindowText(h) or "").lower():
            res.append((h, win32gui.GetWindowRect(h)))
        return True
    win32gui.EnumWindows(cb, None); return res
wins = [(h, r) for h, r in find_wa() if r[0] > -10000] or find_wa()
L, T, R, B = win32gui.GetWindowRect(wins[0][0]); W, H = R - L, B - T
img = ImageGrab.grab().convert("RGB")
# compose: banda inferior del área de chat (a la derecha del sidebar)
crop = img.crop((max(0, L + int(W * 0.30)), max(0, B - 90), min(img.width, R), min(img.height, B)))
crop = crop.resize((crop.width * 3, crop.height * 3))
crop.save(str((OUT / "compose_zoom.png").resolve()))
print(f"[peek] compose_zoom.png  (wa rect={(L,T,R,B)})", flush=True)
