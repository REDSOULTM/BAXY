"""Prepara lotes compactos para que agentes-juez revisen individualmente las
respuestas de las tandas re-run 1-4 (4000 casos).

Lee _rerun_tanda_{0,1000,2000,3000}.jsonl, arma registros compactos (campos que el
juez necesita) y los parte en lotes de BATCH casos -> _judge_batch_NNN.json.

Uso: python scripts/_diag/_make_judge_batches.py [BATCH]
Salida: scripts/_diag/_jbatch/_judge_batch_000.json ... (BATCH casos c/u)
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DIAG = ROOT / "scripts" / "_diag"
OUTDIR = DIAG / "_jbatch"
BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 80
SRC = [DIAG / f"_rerun_tanda_{o}.jsonl" for o in (0, 1000, 2000, 3000)]

rows = []
for f in SRC:
    if not f.exists():
        continue
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        rows.append({
            "i": r.get("i"),
            "cat": r.get("cat"),
            "lang": r.get("lang"),
            "user": (r.get("user_text") or "")[:200],
            "prev": (r.get("prev_text") or "")[:120],
            "reply": (r.get("reply") or "")[:400],
            # tools con action+args recortados (el juez necesita ver QUÉ se ejecutó)
            "tools": [{"n": t.get("name"), "a": t.get("action"),
                       "args": {k: str(v)[:40] for k, v in (t.get("args") or {}).items()}}
                      for t in (r.get("tools") or [])][:12],
            "gt_tools": r.get("correct_tools") or [],
            "also_ok": r.get("also_valid") or [],
            "style": (r.get("correct_reply_style") or "")[:120],
            "dt": r.get("dt"),
            "passes": r.get("passes"),
            "sig": r.get("hard_signals") or [],
        })

OUTDIR.mkdir(parents=True, exist_ok=True)
# limpiar lotes viejos
for old in OUTDIR.glob("_judge_batch_*.json"):
    old.unlink()

n_batches = 0
for bi in range(0, len(rows), BATCH):
    chunk = rows[bi:bi + BATCH]
    out = OUTDIR / f"_judge_batch_{n_batches:03d}.json"
    out.write_text(json.dumps(chunk, ensure_ascii=False), encoding="utf-8")
    n_batches += 1

print(f"{len(rows)} casos -> {n_batches} lotes de {BATCH} en {OUTDIR}")
print(f"primer lote: {(OUTDIR / '_judge_batch_000.json').stat().st_size} bytes")
