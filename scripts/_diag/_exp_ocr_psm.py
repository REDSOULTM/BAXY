"""Medir psm 6 (bloque uniforme, actual) vs psm 11 (sparse text, pensado para UI
dispersa) sobre el MISMO screenshot. Decide si vale cambiar el psm del grounding
de pantalla. NO toca código — solo mide recall de labels UI + latencia.
"""
from __future__ import annotations
import sys, time, shutil, subprocess, io, csv
from pathlib import Path
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

SHOT = Path("scripts/_diag/_ocr/screen.png").resolve()
TESS = shutil.which("tesseract") or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TARGETS = ["File", "Edit", "View", "Run", "Terminal", "PROBLEMS", "OUTPUT",
           "Archivos", "Search", "Selection", "DEBUG", "PORTS"]

def fold(s): return "".join(c for c in s.lower() if c.isalnum())

def run_psm(psm):
    cmd = [TESS, str(SHOT), "stdout", "-l", "spa+eng", "--psm", str(psm), "tsv"]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, timeout=60)
    dt = time.time() - t0
    txt = (proc.stdout or b"").decode("utf-8", errors="replace")
    words = []
    for row in csv.DictReader(io.StringIO(txt), delimiter="\t"):
        raw = str(row.get("text") or "").strip()
        try: conf = float(row.get("conf") or -1)
        except ValueError: conf = -1
        if raw and conf >= 25:
            words.append(fold(raw))
    wordset = set(words)
    found = [t for t in TARGETS if fold(t) in wordset]
    return dt, len(words), found

for psm in (6, 11, 3):
    dt, nwords, found = run_psm(psm)
    print(f"psm {psm:2d}: {dt:.2f}s  words={nwords:3d}  labels {len(found)}/{len(TARGETS)}: {found}", flush=True)
print("[done]", flush=True)
