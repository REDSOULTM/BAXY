"""Re-mide los casos B3/C1/C2 de la tanda 1 contra el CÓDIGO ACTUAL (post-fix loop
"actual" + batch circuit-breaker). El objetivo es ver qué quedó mitigado antes de
escribir cualquier fix nuevo. MEDIR, NO CELEBRAR.

Uso: python scripts/_diag/_remeasure_loops.py
Salida: scripts/_diag/_remeasure_loops.jsonl (un caso por línea, detalle completo).
"""
from __future__ import annotations
import json, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

DATASET = ROOT / "dataset_finetune" / "curated" / "curated.jsonl"
OUT = ROOT / "scripts" / "_diag" / "_remeasure_loops.jsonl"

# Casos exactos de la tanda 1 a re-medir (por índice i = posición en el set único).
GROUPS = {
    "B3": [513, 514, 538, 540, 945],
    "C1": [74, 602, 646, 727, 892],
    "C2": [158, 288, 301, 837, 862],
}
WANT = {i: g for g, ids in GROUPS.items() for i in ids}

# Reconstruir el set único en el MISMO orden que el harness de cacería.
rows_all, seen = [], set()
for line in DATASET.read_text(encoding="utf-8", errors="replace").splitlines():
    if not line.strip():
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    ut = (d.get("user_text") or "").strip()
    if not ut:
        continue
    key = (ut.lower(), (d.get("prev_text") or "").strip().lower())
    if key in seen:
        continue
    seen.add(key)
    rows_all.append(d)

cases = [(i, rows_all[i]) for i in sorted(WANT) if i < len(rows_all)]
print(f"[remeasure] {len(cases)} casos: {sorted(WANT)}", flush=True)

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)

from gemma4_agent.tools_pkg.tools import ToolRegistry, COMPOUND_TOOL_SCHEMAS
from gemma4_agent.infra import llm_client
from gemma4_agent.support.reasoning import detect_leaked_tool_call

KNOWN = {s["function"]["name"] for s in COMPOUND_TOOL_SCHEMAS
         if isinstance(s, dict) and isinstance(s.get("function"), dict)}

executed: list = []
def _mock_execute(self, n, a):
    executed.append({"name": n, "args": a or {}})
    return {"ok": True, "status": "ok", "verified": True, "_eval_mock": True}
ToolRegistry.execute = _mock_execute
if hasattr(ToolRegistry, "t_computer_use"):
    ToolRegistry.t_computer_use = lambda self, a: (
        executed.append({"name": "computer_use", "args": a or {}}) or
        {"ok": True, "status": "ok", "verified": True, "completion_status": "simulated"})
for _m in ["gui_type", "gui_keypress", "gui_click", "gui_type_into", "gui_click_button",
           "gui_hotkey", "gui_scroll", "gui_drag", "_send_text_via_sendinput"]:
    if hasattr(ToolRegistry, _m):
        setattr(ToolRegistry, _m, lambda *a, **k: {"ok": True})

ncalls = [0]
_real_chat = llm_client.LLMClient.chat
def _wrap(self, m, **kw):
    ncalls[0] += 1
    return _real_chat(self, m, **kw)
llm_client.LLMClient.chat = _wrap

from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent()
agent.run_content("hola")  # warm

OUT.parent.mkdir(parents=True, exist_ok=True)
if OUT.exists():
    OUT.unlink()
with OUT.open("a", encoding="utf-8") as out:
    for i, d in cases:
        grp = WANT[i]
        ut = (d.get("user_text") or "").strip()
        prev = (d.get("prev_text") or "").strip()
        try:
            agent.history.clear()
        except Exception:
            pass
        if prev:
            try:
                agent.run_content(prev)
            except Exception:
                pass
        executed.clear(); ncalls[0] = 0
        err = None
        t0 = time.perf_counter()
        try:
            rep = agent.run_content(ut)
            content = getattr(rep, "content", "") or ""
        except Exception as e:
            content = ""; err = f"{type(e).__name__}: {e}"
        dt = time.perf_counter() - t0
        rec = {
            "i": i, "group": grp, "user_text": ut, "prev_text": prev,
            "dt": round(dt, 2), "passes": ncalls[0], "ntools": len(executed),
            "tools": [{"name": e["name"], "action": (e["args"] or {}).get("action")}
                      for e in executed],
            "reply": content, "err": err,
        }
        out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()
        loop = "LOOP" if len(executed) > 8 else "ok"
        print(f"  [{grp}] i={i} dt={dt:.1f}s ntools={len(executed)} {loop}  {ut[:50]!r}", flush=True)

print(f"[done] -> {OUT.name}", flush=True)
