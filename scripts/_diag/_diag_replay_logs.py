"""Re-corre los mensajes REALES del usuario (de router_corpus_real_logs.jsonl) contra
el agente+LLM real para cazar bugs/latencia/calidad. Ejecución física MOCKEADA (seguro:
cero SendInput/efectos). Captura por mensaje: latencia, #pasadas LLM, tools ejecutadas,
reply, + DETECTA issues. Escribe incremental a _replay_results.jsonl.

Uso: python scripts/_diag/_diag_replay_logs.py [LIMIT] [OFFSET]
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

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 1000000
OFFSET = int(sys.argv[2]) if len(sys.argv) > 2 else 0
CORPUS = ROOT / "gemma4_agent" / "data" / "router_corpus_real_logs.jsonl"
OUT = ROOT / "_replay_results.jsonl"

msgs = []
seen = set()
for line in CORPUS.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    q = (json.loads(line).get("q") or "").strip()
    if q and q not in seen:
        seen.add(q); msgs.append(q)
msgs = msgs[OFFSET:OFFSET + LIMIT]
print(f"[replay] {len(msgs)} mensajes (offset={OFFSET})", flush=True)

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
mgr = get_shared_manager(); print("[boot]...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)

from gemma4_agent.tools_pkg.tools import ToolRegistry, COMPOUND_TOOL_SCHEMAS
from gemma4_agent.infra import llm_client
from gemma4_agent.support.reasoning import detect_leaked_tool_call

KNOWN = {s["function"]["name"] for s in COMPOUND_TOOL_SCHEMAS
         if isinstance(s, dict) and isinstance(s.get("function"), dict)}
executed: list = []
ToolRegistry.execute = lambda self, n, a: (executed.append(n) or {"ok": True, "status": "ok", "_eval_mock": True})
for _m in ["gui_type", "gui_keypress", "gui_click", "gui_type_into", "gui_click_button",
           "gui_hotkey", "gui_scroll", "gui_drag", "_send_text_via_sendinput"]:
    if hasattr(ToolRegistry, _m):
        setattr(ToolRegistry, _m, lambda *a, **k: {"ok": True})

ncalls = [0]
_real = llm_client.LLMClient.chat
def _w(self, m, **kw):
    ncalls[0] += 1
    return _real(self, m, **kw)
llm_client.LLMClient.chat = _w

from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent()
agent.run_content("hola")  # warm

_LEAK_TOKENS = re.compile(r"<intent>|</intent>|<unused\d+>|<\|tool_call|INTENT:")

def find_issues(msg, reply, passes, executed_tools, dt, err):
    issues = []
    if err:
        issues.append("ERROR:" + err[:50])
        return issues
    r = (reply or "").strip()
    if not r:
        issues.append("empty_reply")
    if _LEAK_TOKENS.search(reply or ""):
        issues.append("special_token_leak")
    try:
        if detect_leaked_tool_call(reply or "", known_tool_names=KNOWN) is not None:
            issues.append("tool_call_leaked_in_reply")
    except Exception:
        pass
    if passes >= 4:
        issues.append(f"many_passes({passes})")
    if dt > 6.0:
        issues.append(f"slow({dt:.1f}s)")
    return issues

if OUT.exists() and OFFSET == 0:
    OUT.unlink()
t_start = time.time()
n_issues = 0
with OUT.open("a", encoding="utf-8") as out:
    for i, msg in enumerate(msgs):
        try:
            agent.history.clear()
        except Exception:
            pass
        executed.clear(); ncalls[0] = 0
        err = None
        t0 = time.perf_counter()
        try:
            reply = agent.run_content(msg)
            content = getattr(reply, "content", "") or ""
        except Exception as e:
            content = ""; err = f"{type(e).__name__}: {e}"
        dt = time.perf_counter() - t0
        issues = find_issues(msg, content, ncalls[0], list(executed), dt, err)
        if issues:
            n_issues += 1
        rec = {"i": i + OFFSET, "msg": msg, "dt": round(dt, 2), "passes": ncalls[0],
               "tools": list(executed), "reply": content[:140], "issues": issues}
        out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()
        if (i + 1) % 25 == 0:
            el = time.time() - t_start
            print(f"  {i+1}/{len(msgs)}  issues={n_issues}  {el/(i+1):.1f}s/msg  ETA {el/(i+1)*(len(msgs)-i-1)/60:.0f}min", flush=True)

print(f"[done] {len(msgs)} corridos, {n_issues} con issues, {(time.time()-t_start)/60:.1f}min", flush=True)
