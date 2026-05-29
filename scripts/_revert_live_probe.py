"""Probe EN VIVO contra el server con la config 27-may revertida.
Llama agent.run_content con 6 mensajes diversos para reproducir el patron
de uso real (saludo, info, tool simple, tool con thinking, charla, info).
Reporta latencia por turno + cualquier error/crash.
"""
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.agent_core.agent import Gemma4Agent

print("[probe] cargando agente...", flush=True)
agent = Gemma4Agent()

PROMPTS = [
    "Hola, decime algo corto.",
    "Que dia es hoy?",
    "Cuanto es 23 mas 47?",
    "Decime el clima en Buenos Aires.",
    "Que opinas del futbol?",
    "Cual es la capital de Francia?",
]

results = []
t_start = time.time()
for i, prompt in enumerate(PROMPTS, 1):
    print(f"\n[probe] === turn {i}/{len(PROMPTS)}: {prompt!r} ===", flush=True)
    t0 = time.time()
    try:
        reply = agent.run_content(prompt)
        dt = time.time() - t0
        content = getattr(reply, "content", "") or ""
        err_field = getattr(reply, "error", None)
        ok = bool(content.strip()) and not err_field
        snippet = content[:120].replace("\n", " ")
        results.append({"turn": i, "ok": ok, "dt": dt, "err": err_field, "reply": snippet})
        tag = "OK " if ok else "FAIL"
        print(f"[probe] turn {i} {tag} dt={dt:.2f}s reply={snippet!r} err={err_field!r}", flush=True)
    except Exception as e:
        dt = time.time() - t0
        err = f"{type(e).__name__}: {e}"
        results.append({"turn": i, "ok": False, "dt": dt, "err": err, "reply": None})
        print(f"[probe] turn {i} EXCEPTION dt={dt:.2f}s err={err}", flush=True)
        traceback.print_exc()

total = time.time() - t_start
ok_count = sum(1 for r in results if r["ok"])
print(f"\n[probe] DONE total={total:.1f}s ok={ok_count}/{len(results)}", flush=True)
for r in results:
    flag = "OK " if r["ok"] else "FAIL"
    err = f" err={r['err']}" if r["err"] else ""
    print(f"  turn {r['turn']} {flag} dt={r['dt']:.2f}s{err}", flush=True)
