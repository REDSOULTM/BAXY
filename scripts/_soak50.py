"""Soak de 50 turnos MIXTOS (smalltalk / info / acción-volumen / ventana) con el
cache-hit default ON. Gate del research compass + 'todo lo posible'. Mide:
  - CRASHES (excepciones / server caído) -> debe ser 0
  - RUNAWAYS (calls>2 en un turno) -> el success-gating debe evitarlos
  - cache-hit rate de la pass-2 de acciones
  - latencia p50/p90 por tipo
  - replies vacíos/garbled

Acciones benignas/reversibles (volumen se restaura al final; ventana=minimizar).
No clear de history (uso real; el context_router maneja el crecimiento).

  python scripts/_soak50.py
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
mgr = get_shared_manager()
print(f"[boot] {prof.name}; server...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra import llm_client

calls_this_turn = {"n": 0, "last_prompt_n": None, "last_cache_n": None}
orig = llm_client.LLMClient.chat


def wrapped(self, messages, **kw):
    resp = orig(self, messages, **kw)
    calls_this_turn["n"] += 1
    t = (resp or {}).get("timings", {})
    calls_this_turn["last_prompt_n"] = t.get("prompt_n")
    calls_this_turn["last_cache_n"] = t.get("cache_n")
    return resp


llm_client.LLMClient.chat = wrapped
print("[boot] agente...", flush=True)
agent = Gemma4Agent()

SMALLTALK = ["hola", "gracias", "buenas", "todo bien?", "qué tal"]
INFO = ["qué es la fotosíntesis", "cuál es la capital de Japón", "explicame qué es una API",
        "por qué llueve", "qué es el ADN"]
VOL = [f"poné el volumen al {v} por ciento" for v in (30, 45, 60, 25, 50, 40, 35, 55)]
WIN = ["minimizá la ventana", "minimizá la calculadora"]

# Build a 50-turn mixed sequence cycling the types.
SEQ = []
import itertools
pools = [SMALLTALK, INFO, VOL, WIN]
idx = [0, 0, 0, 0]
order = list(itertools.islice(itertools.cycle([2, 1, 2, 0, 2, 1, 3, 2, 1, 0]), 50))  # action-heavy
for k in order:
    pool = pools[k]
    SEQ.append(pool[idx[k] % len(pool)])
    idx[k] += 1

stats = {"crashes": 0, "runaways": 0, "bad": 0, "action_hits": 0, "action_turns": 0}
lat = {"smalltalk": [], "info": [], "action": [], "window": []}


def kind(cmd):
    if cmd in SMALLTALK:
        return "smalltalk"
    if cmd in INFO:
        return "info"
    if cmd in WIN:
        return "window"
    return "action"


print(f"[soak] {len(SEQ)} turnos...", flush=True)
t_start = time.monotonic()
for i, cmd in enumerate(SEQ):
    calls_this_turn["n"] = 0
    calls_this_turn["last_prompt_n"] = None
    calls_this_turn["last_cache_n"] = None
    t0 = time.monotonic()
    try:
        reply = agent.run_content(cmd)
        content = (getattr(reply, "content", "") or "")
        err = getattr(reply, "error", None)
    except Exception as e:  # noqa: BLE001
        stats["crashes"] += 1
        print(f"  [CRASH t{i}] {cmd!r}: {type(e).__name__}: {e}", flush=True)
        continue
    dt = time.monotonic() - t0
    k = kind(cmd)
    lat[k].append(dt)
    runaway = calls_this_turn["n"] > 2
    badrep = (not content.strip()) or err or ("think" in content.lower()[:20])
    if runaway:
        stats["runaways"] += 1
    if badrep:
        stats["bad"] += 1
    if k == "action":
        stats["action_turns"] += 1
        cn = calls_this_turn["last_cache_n"]
        pn = calls_this_turn["last_prompt_n"]
        if isinstance(pn, int) and pn < 500:  # pass-2 cache hit
            stats["action_hits"] += 1
    flag = "" if not (runaway or badrep) else "  <-- CHK"
    if i % 5 == 0 or runaway or badrep:
        print(f"  t{i:02d} [{k:9}] {cmd[:30]!r:32} dt={dt:.2f}s calls={calls_this_turn['n']}{flag}", flush=True)

# restore volume to a neutral level
try:
    agent.run_content("poné el volumen al 30 por ciento")
except Exception:
    pass


def pct(xs, p):
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(len(s) - 1, int(len(s) * p))]


print("=" * 92, flush=True)
print(f"[SOAK 50] wall={time.monotonic()-t_start:.0f}s", flush=True)
print(f"  crashes={stats['crashes']}  runaways={stats['runaways']}  bad_replies={stats['bad']}", flush=True)
print(f"  action pass-2 cache-hits={stats['action_hits']}/{stats['action_turns']}", flush=True)
for k in ("smalltalk", "info", "action", "window"):
    xs = lat[k]
    print(f"  {k:9} n={len(xs):2d} p50={pct(xs,0.5):.2f}s p90={pct(xs,0.9):.2f}s", flush=True)
print("=" * 92, flush=True)
print("[GATE] crashes=0 + runaways=0 + bad=0 + cache-hits altos = cache fix robusto a escala.", flush=True)
