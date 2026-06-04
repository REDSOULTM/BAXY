"""Mide cuántos turnos REALES del dataset (6162, ya corridos en las 4 runs)
serían flageados por el guard #1. Es la prueba de falso-positivo en habla real:
si flagea muchos turnos legítimos, NO ponerlo ON. Si flagea ~0 (o solo mentiras
reales), es seguro.

Reconstruye por turno: user_text + reply + tools ejecutadas (de los _finetune_eval
_results_*.jsonl) y aplica intent_domain_mismatch.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gemma4_agent.safety_pkg.reply_validator import intent_domain_mismatch as q

ROOT = Path(__file__).resolve().parents[2]
RUNS = [
    "_finetune_eval_results_run1_stratified.jsonl",
    "_finetune_eval_results_run2_fresh.jsonl",
    "_finetune_eval_results_run3.jsonl",
    "_finetune_eval_results_run4_fresh.jsonl",
]


def tools_as_calls(tools_exec):
    # el eval guardó tools_exec como lista de nombres; result desconocido ->
    # asumimos exitoso (el caso peor para el guard: maximiza la chance de flagear).
    return [{"name": n, "result": {"ok": True, "status": "done", "verified": True}}
            for n in (tools_exec or [])]


seen = set()
total = flagged = 0
hits = []
for fn in RUNS:
    p = ROOT / fn
    if not p.exists():
        continue
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        key = (d.get("user_text", "").lower(), (d.get("prev_text") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        total += 1
        ut = d.get("user_text", "")
        reply = d.get("reply", "")
        calls = tools_as_calls(d.get("tools_exec"))
        if q(ut, reply, calls):
            flagged += 1
            hits.append((ut, d.get("tools_exec"), reply[:80]))

print(f"Turnos únicos del dataset evaluados: {total}")
print(f"Flageados por el guard #1: {flagged} ({100*flagged/max(total,1):.2f}%)")
print("\n=== TODOS los flageados (revisar si son mentiras reales o falsos+) ===")
for ut, tools, rep in hits:
    print(f"  user={ut[:42]!r}")
    print(f"    tools={tools} reply={rep!r}")
