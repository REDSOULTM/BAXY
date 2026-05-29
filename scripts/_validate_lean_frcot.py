"""Validacion EN VIVO de lean prompt mode + FR-CoT contra el agente REAL.

Por comando reporta: qué tool_calls emitió el modelo (mis-routing?), el reply, si se
FILTRÓ el formato FR-CoT (INTENT/TOOL/ARGS) al reply visible (el bug que rompió media),
y latencia. La config se controla por env ANTES de correr:
  baseline:   (sin flags)
  lean:       GEMMA4_LEAN_RULES=1
  frcot:      GEMMA4_FRCOT=1
  lean+frcot: ambos
Usa run_content (= la UI, seguro, sin SendInput).
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

_calls: list[str] = []
orig_chat = llm_client.LLMClient.chat


def wrapped_chat(self, messages, **kw):
    resp = orig_chat(self, messages, **kw)
    try:
        for ch in (resp or {}).get("choices") or []:
            for tc in (ch.get("message") or {}).get("tool_calls") or []:
                fn = (tc.get("function") or {}).get("name")
                if fn:
                    _calls.append(fn)
    except Exception:
        pass
    return resp


llm_client.LLMClient.chat = wrapped_chat

cfg = (f"LEAN={os.environ.get('GEMMA4_LEAN_RULES','-')} "
       f"FRCOT={os.environ.get('GEMMA4_FRCOT','-')} "
       f"FA={os.environ.get('GEMMA4_FLASH_ATTN','off(default)')}")
print(f"[validate] config: {cfg} | cargando agente...", flush=True)
agent = Gemma4Agent()
try:
    from gemma4_agent.agent_core import agent_prompt as _ap
    print(f"[validate] core rules always-on: {sorted(_ap.CORE_TOOL_RULE_NAMES)}", flush=True)
except Exception:
    pass

# bloque FR-CoT filtrado al reply (lo que NO debe pasar)
_FRCOT_LEAK = re.compile(r"(?is)\bINTENT:\s*\S.*?\bTOOL:.*?\bARGS:")

# (comando, tool(s) esperado(s) — para chequear mis-routing a ojo)
CASES = [
    ("Hola, todo bien?", "chat (sin tool)"),
    ("Que hora es?", "system"),
    ("Pone algo de musica", "media (random)"),
    ("Pon Bohemian Rhapsody en Spotify", "media (provider=spotify)"),
    ("Pausa la musica", "media/audio"),
    ("Subi el volumen al 60", "audio set_volume"),
    ("Mutea el sonido", "audio mute"),
    ("Abri Spotify", "app open"),
    ("Anda a la pagina de YouTube", "browser/app"),
    ("Subi el brillo de la pantalla", "device_settings/system"),
    ("Mandale a mama por whatsapp que llego tarde", "whatsapp send_message"),
    ("Sacame una captura de pantalla", "gui screenshot"),
    ("Cuando diga banana, subi el volumen", "routine create on_phrase"),
]

print("=" * 96, flush=True)
results = []
for i, (cmd, expected) in enumerate(CASES, 1):
    _calls.clear()
    t0 = time.time()
    leak = False
    try:
        reply = agent.run_content(cmd)
        content = (getattr(reply, "content", "") or "")
        err = getattr(reply, "error", None)
        leak = bool(_FRCOT_LEAK.search(content))
    except Exception as e:
        content = f"EXCEPTION: {type(e).__name__}: {e}"
        err = "exc"
    dt = time.time() - t0
    tools = ",".join(_calls) if _calls else "(NINGUNO)"
    snip = content.replace("\n", " ")[:84]
    results.append({"i": i, "dt": dt, "tools": tools, "leak": leak, "err": err})
    leakflag = "  <<< FR-CoT LEAK!" if leak else ""
    print(f"[{i:2d}] {cmd!r}", flush=True)
    print(f"     esperado~={expected} | tools={tools} | dt={dt:.2f}s | err={err}{leakflag}", flush=True)
    print(f"     reply: {snip!r}", flush=True)
    print("-" * 96, flush=True)

dts = sorted(r["dt"] for r in results)
n = len(dts)
leaks = sum(1 for r in results if r["leak"])
notool = sum(1 for r in results if r["tools"] == "(NINGUNO)")
print(f"[validate] {cfg}", flush=True)
print(f"[validate] turns={n} p50={dts[n//2]:.2f}s p90={dts[min(n-1,int(n*0.9))]:.2f}s "
      f"max={dts[-1]:.2f}s | FR-CoT leaks={leaks} | turns sin tool={notool}", flush=True)
print("[validate] NOTA: 'routine banana' creó un routine de prueba — borrar con "
      "routine(action='delete') si molesta.", flush=True)
