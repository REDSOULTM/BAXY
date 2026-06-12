"""Muestra la trayectoria de validación interna del trainer de wake."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
d = json.load(open(ROOT / "output" / "baxy" / "baxy_metrics.json", encoding="utf-8"))
for phase in (1, 2, 3):
    rows = [r for r in d if r.get("phase") == phase]
    if not rows:
        continue
    print(f"Phase {phase} (ultimos 6):")
    for r in rows[-6:]:
        print(f"  step {r['step']:6}  recall={r['recall']:.3f}  "
              f"fpph={r['fpph']:.2f}  acc={r['accuracy']:.3f}")
