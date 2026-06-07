"""Convierte un _hunt_tanda_<OFFSET>.jsonl en un input trim para el juez LLM.
Mismo formato que la tanda 1 (campos: i/cat/lang/user/prev/reply/tools/dt/passes/
gt_tools/signals). Recorta el reply para no inflar el prompt del juez.

Uso: python scripts/_diag/_make_judge_input.py <OFFSET>
  ej: python scripts/_diag/_make_judge_input.py 1000
Salida: scripts/_diag/_judge_input_<OFFSET>.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OFFSET = int(sys.argv[1]) if len(sys.argv) > 1 else 0
SRC = ROOT / "scripts" / "_diag" / f"_hunt_tanda_{OFFSET}.jsonl"
DST = ROOT / "scripts" / "_diag" / f"_judge_input_{OFFSET}.json"

out = []
for line in SRC.read_text(encoding="utf-8", errors="replace").splitlines():
    if not line.strip():
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    out.append({
        "i": d.get("i"),
        "cat": d.get("cat", "?"),
        "lang": d.get("lang", "?"),
        "user": (d.get("user_text") or "")[:300],
        "prev": (d.get("prev_text") or "")[:200],
        "reply": (d.get("reply") or "")[:600],
        "tools": [{"n": t.get("name"), "a": t.get("action")}
                  for t in (d.get("tools") or [])[:12]],
        "dt": d.get("dt"),
        "passes": d.get("passes"),
        "gt_tools": d.get("correct_tools") or [],
        "signals": d.get("hard_signals") or [],
    })

DST.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(f"[judge-input] {len(out)} casos -> {DST.name}")
# resumen rapido de señales duras (sin LLM): para priorizar
from collections import Counter
sig = Counter()
slow = sum(1 for o in out if (o["dt"] or 0) > 5)
veryslow = sum(1 for o in out if (o["dt"] or 0) > 8)
empty = sum(1 for o in out if not (o["reply"] or "").strip())
for o in out:
    for s in o["signals"]:
        sig[s.split("(")[0]] += 1
print(f"  señales duras: {dict(sig)}")
print(f"  reply vacío: {empty} | slow>5s: {slow} | very_slow>8s: {veryslow}")
