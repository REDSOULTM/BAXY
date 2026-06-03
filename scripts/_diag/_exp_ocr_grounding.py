"""Medir el PRIMITIVO de grounding por OCR (Tesseract) que ya usa la cascada
(_click_button_via_ocr → ocr_find_text). Read-only: NO clickea, NO LLM.

Sobre el screenshot actual:
  - latencia de ocr_image (Tesseract --psm 6 sobre full screen)
  - para varios targets de texto VISIBLE: ¿found? ¿caja? ¿el centro cae bien?
Dibuja la caja + un crosshair en el centro del click candidato → guarda imagen
anotada para LEER (Read tool) y juzgar si el click aterrizaría en el elemento.
"""
from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
from PIL import ImageGrab, ImageDraw
from gemma4_agent.tools_pkg.ops_tools import ocr_image, ocr_find_text

OUT = Path("scripts/_diag/_ocr"); OUT.mkdir(parents=True, exist_ok=True)
shot = ImageGrab.grab().convert("RGB")
shot_path = (OUT / "screen.png").resolve()
shot.save(str(shot_path))
print(f"[shot] {shot.size}", flush=True)

# --- latencia OCR full-screen ---
t0 = time.time(); res = ocr_image(shot_path); dt = time.time() - t0
if not res.get("ok"):
    print("[ocr_image] FALLO:", res); sys.exit(1)
print(f"[ocr_image] {dt:.2f}s  words={res['word_count']} lines={res['line_count']}", flush=True)

# muestra de líneas detectadas (calidad cruda)
print("  muestra de líneas OCR:", flush=True)
for ln in res.get("lines", [])[:12]:
    print(f"    '{str(ln.get('text',''))[:50]}' conf={ln.get('conf')}", flush=True)

# --- targets de texto que suelen estar visibles en VS Code ---
TARGETS = ["File", "Edit", "View", "Run", "Terminal", "PROBLEMS", "OUTPUT",
           "Archivos", "Search", "Selection"]
img = shot.copy(); d = ImageDraw.Draw(img)
print("\n[grounding por target]", flush=True)
hits = 0
for tgt in TARGETS:
    t0 = time.time(); f = ocr_find_text(shot_path, tgt); ft = time.time() - t0
    matches = f.get("matches", []) if f.get("ok") else []
    if matches:
        m = matches[0]
        cx, cy = m.get("center_x"), m.get("center_y")
        l, t, w, h = m.get("left"), m.get("top"), m.get("width"), m.get("height")
        d.rectangle([l, t, l + w, t + h], outline=(255, 0, 0), width=2)
        d.line([cx - 8, cy, cx + 8, cy], fill=(0, 255, 0), width=2)
        d.line([cx, cy - 8, cx, cy + 8], fill=(0, 255, 0), width=2)
        d.text((l, t - 12), tgt, fill=(255, 255, 0))
        print(f"  ✓ {tgt:12s} found  center=({cx},{cy}) conf={m.get('conf')}  ({ft:.2f}s)", flush=True)
        hits += 1
    else:
        print(f"  ✗ {tgt:12s} NOT found  ({ft:.2f}s)", flush=True)
img.save(str((OUT / "annotated.png").resolve()))
print(f"\n[resumen] {hits}/{len(TARGETS)} targets localizados. Anotada: scripts/_diag/_ocr/annotated.png", flush=True)
print("[done]", flush=True)
