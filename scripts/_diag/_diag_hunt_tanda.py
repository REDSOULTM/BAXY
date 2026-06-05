"""Cacería profunda por TANDAS: corre N casos del dataset contra el LLM real,
guarda el detalle COMPLETO de cada caso (reply entero + tools con args + latencia +
passes + señales de fallo) para que un juez LLM lo evalúe caso por caso.

A diferencia de _diag_finetune_dataset_eval (que trunca el reply y solo guarda
nombres de tool), este guarda lo necesario para juzgar CALIDAD/HONESTIDAD/LATENCIA.

Uso: python scripts/_diag/_diag_hunt_tanda.py <OFFSET> <LIMIT>
  ej: python scripts/_diag/_diag_hunt_tanda.py 0 1000   (tanda 1: casos 0-999)
Salida: scripts/_diag/_hunt_tanda_<OFFSET>.jsonl (un caso por línea, detalle completo)
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
# El eval mide ROUTING sin fricción: con safety ON (ahora default), toda op
# destructiva daría needs_confirmation y ensuciaría la medición de qué tool eligió el
# 4B. Lo desactivamos SOLO acá (el harness), no en producción. La confirmación real
# se verifica aparte en vivo (_verify_confirm_gate_live.py).
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")

OFFSET = int(sys.argv[1]) if len(sys.argv) > 1 else 0
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
DATASET = ROOT / "dataset_finetune" / "curated" / "curated.jsonl"
# Prefijo de salida configurable (env GEMMA4_HUNT_PREFIX) para no pisar los hunts
# originales pre-fix: el re-run final usa prefijo "_rerun_tanda_".
_PREFIX = os.environ.get("GEMMA4_HUNT_PREFIX", "_hunt_tanda_")
OUT = ROOT / "scripts" / "_diag" / f"{_PREFIX}{OFFSET}.jsonl"

# Cargar ejemplos ÚNICOS por (user_text, prev_text), orden estable del dataset.
rows, seen = [], set()
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
    rows.append(d)
rows = rows[OFFSET:OFFSET + LIMIT]
print(f"[hunt] tanda OFFSET={OFFSET} LIMIT={LIMIT} -> {len(rows)} casos", flush=True)

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

# Mock que captura NOMBRE + ARGS de cada tool (read-only: no efecto físico).
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

_LEAK = re.compile(r"<intent>|</intent>|<unused\d+>|<\|tool_call|INTENT:")
_OLD = re.compile(r"\bsoy gemma\b|\bme llamo gemma\b", re.IGNORECASE)


def hard_signals(reply, passes, exe, dt, err):
    """Detectores DUROS (precisos, sin falsos+) — los baratos. La CALIDAD la juzga
    el LLM aparte."""
    s = []
    if err:
        return ["ERROR:" + err[:60]]
    r = (reply or "").strip()
    if not r:
        s.append("empty_reply")
    if _LEAK.search(reply or ""):
        s.append("token_leak")
    if _OLD.search(reply or ""):
        s.append("old_name")
    try:
        if detect_leaked_tool_call(reply or "", known_tool_names=KNOWN) is not None:
            s.append("tool_call_leaked")
    except Exception:
        pass
    if len(exe) > 8:
        s.append(f"tool_loop({len(exe)})")
    if passes >= 4:
        s.append(f"many_passes({passes})")
    if dt > 8.0:
        s.append(f"very_slow({dt:.1f}s)")
    elif dt > 5.0:
        s.append(f"slow({dt:.1f}s)")
    return s


OUT.parent.mkdir(parents=True, exist_ok=True)
if OUT.exists():
    OUT.unlink()
t0g = time.time()
with OUT.open("a", encoding="utf-8") as out:
    for i, d in enumerate(rows):
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
        sig = hard_signals(content, ncalls[0], executed, dt, err)
        rec = {
            "i": OFFSET + i, "cat": d.get("category", "?"), "lang": d.get("lang", "?"),
            "user_text": ut, "prev_text": prev,
            "correct_tools": d.get("correct_tools") or [],
            "also_valid": d.get("also_valid") or [],
            "correct_reply_style": (d.get("correct_reply_style") or "")[:160],
            "dt": round(dt, 2), "passes": ncalls[0],
            "tools": [{"name": e["name"], "action": (e["args"] or {}).get("action"),
                       "args": {k: str(v)[:60] for k, v in (e["args"] or {}).items() if k != "action"}}
                      for e in executed],
            "reply": content,           # COMPLETO (para el juez)
            "hard_signals": sig,
        }
        out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()
        if (i + 1) % 50 == 0:
            el = time.time() - t0g
            print(f"  {i+1}/{len(rows)}  {el/(i+1):.1f}s/caso  ETA {el/(i+1)*(len(rows)-i-1)/60:.0f}min", flush=True)

print(f"[done] {len(rows)} casos en {(time.time()-t0g)/60:.1f}min -> {OUT.name}", flush=True)
