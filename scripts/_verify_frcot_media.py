"""Verificacion EN VIVO de FR-CoT en el dominio MEDIA (el que rompio en el
intento previo) + deteccion de leak del formato INTENT:/TOOL:/ARGS:/GO al reply.

Correr con el server FA-off arriba. Dos modos (mismo proceso NO sirve: el flag
se lee al construir el prompt por turno, pero comparamos corridas separadas para
no contaminar el historial):
  python scripts/_verify_frcot_media.py            # usa el estado de GEMMA4_FRCOT del env
Gates (SPRINT_frcot_latencia_accion.md):
  (a) tool_calls correctos en media >= baseline; (b) 0 leak del bloque FR-CoT
  en el reply visible; (c) dt no peor que baseline.
"""
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra import llm_client

_turn_tool_calls: list[str] = []
orig_chat = llm_client.LLMClient.chat


def wrapped_chat(self, messages, **kw):
    resp = orig_chat(self, messages, **kw)
    try:
        for ch in (resp or {}).get("choices") or []:
            msg = ch.get("message") or {}
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {}).get("name")
                if fn:
                    _turn_tool_calls.append(fn)
    except Exception:
        pass
    return resp


llm_client.LLMClient.chat = wrapped_chat

_LEAK_RE = re.compile(r"\b(INTENT|TOOL|ARGS)\s*:|(?:^|\s)GO\s*$", re.MULTILINE)

print(f"[frcot-media] GEMMA4_FRCOT={os.environ.get('GEMMA4_FRCOT', '(unset)')}", flush=True)
agent = Gemma4Agent()

CASES = [
    ("Pone musica", "media"),
    ("Pausa la musica", "media"),
    ("Siguiente cancion", "media"),
    ("Pone Bohemian Rhapsody en Spotify", "media"),
]

leaks = 0
print("=" * 90, flush=True)
for i, (cmd, expected) in enumerate(CASES, 1):
    _turn_tool_calls.clear()
    t0 = time.time()
    try:
        reply = agent.run_content(cmd)
        content = (getattr(reply, "content", "") or "")
        err = getattr(reply, "error", None)
    except Exception as e:
        content = f"EXCEPTION: {type(e).__name__}: {e}"
        err = "exc"
    dt = time.time() - t0
    tools = ",".join(_turn_tool_calls) if _turn_tool_calls else "(NINGUNO)"
    leak = bool(_LEAK_RE.search(content))
    leaks += int(leak)
    flat = content.replace("\n", " ")[:90]
    print(f"[{i}] {cmd!r}", flush=True)
    print(f"    esperado~={expected} | tool_calls={tools} | dt={dt:.2f}s | err={err} | LEAK={leak}", flush=True)
    print(f"    reply: {flat!r}", flush=True)
    print("-" * 90, flush=True)

print(f"[frcot-media] leaks={leaks}/4", flush=True)
