"""Verificacion EN VIVO de tool-calling con Plan A2 (core rules reducido).

Riesgo de Plan A2: al sacar reglas del set always-on, un comando que use uno de
esos tools podria dejar de rutear/usar bien. PERO la regla del tool del subset
sigue inyectandose on-demand (build_tool_rules_extras_for_user_msg). Este script
verifica eso EN VIVO: corre comandos que apuntan a tools cuya regla YA NO esta
always-on (media, browser, whatsapp, gui, device_settings, vision) y reporta:
  - que tool_calls REALMENTE emitio el modelo (hook a la respuesta de chat)
  - el reply final

Correr con el server FA-off ya arriba + GEMMA4_CORE_RULES reducido:
  $env:GEMMA4_CORE_RULES="session,system,audio,app,web,window"
  python scripts/_verify_a2_quality.py
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.agent_core import agent_prompt
from gemma4_agent.infra import llm_client

# Confirmar que el set reducido se aplico (mostrar las reglas always-on activas).
print(f"[verify] CORE_TOOL_RULE_NAMES activos ({len(agent_prompt.CORE_TOOL_RULE_NAMES)}): "
      f"{sorted(agent_prompt.CORE_TOOL_RULE_NAMES)}", flush=True)

# Hook a la respuesta de chat para capturar los tool_calls que emite el modelo.
_turn_tool_calls: list[str] = []
orig_chat = llm_client.LLMClient.chat


def wrapped_chat(self, messages, **kw):
    resp = orig_chat(self, messages, **kw)
    try:
        choices = (resp or {}).get("choices") or []
        for ch in choices:
            msg = ch.get("message") or {}
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {}).get("name")
                if fn:
                    _turn_tool_calls.append(fn)
    except Exception:
        pass
    return resp


llm_client.LLMClient.chat = wrapped_chat

# chat_stream (pasada con TTS sink / streaming) emite tool_calls que el hook de
# arriba NO ve. Capturamos los eventos finales del stream tambien.
orig_chat_stream = llm_client.LLMClient.chat_stream


def wrapped_chat_stream(self, messages, **kw):
    for ev in orig_chat_stream(self, messages, **kw):
        try:
            for tc in (ev.get("tool_calls") or []):
                fn = (tc.get("function") or {}).get("name")
                if fn:
                    _turn_tool_calls.append(fn + "*")  # * = via stream
        except Exception:
            pass
        yield ev


llm_client.LLMClient.chat_stream = wrapped_chat_stream

# Ground truth: que tool EJECUTO realmente (independiente del path LLM que la
# emitio). Observador pasivo, no mockea nada — las tools corren de verdad.
from gemma4_agent.tools_pkg.tools import ToolRegistry

_turn_tools_exec: list[str] = []
_orig_execute = ToolRegistry.execute


def _observed_execute(self, name, args):
    _turn_tools_exec.append(str(name))
    return _orig_execute(self, name, args)


ToolRegistry.execute = _observed_execute

print("[verify] cargando agente...", flush=True)
agent = Gemma4Agent()

# (comando, tool(s) esperado(s) cuya regla NO esta always-on en Plan A2)
CASES = [
    ("Pone algo de musica", "media"),
    ("Abri Spotify y pone rock", "media/app"),
    ("Abri YouTube en el navegador", "browser/app"),
    ("Mandale un mensaje a Juan por WhatsApp que ya llego", "whatsapp"),
    ("Sacame una captura de pantalla", "gui"),
    ("Subi el brillo de la pantalla", "device_settings/system"),
    ("Que hay en la pantalla?", "gui/vision"),
    ("Conectate al wifi de casa", "network/device_settings"),
]

print("=" * 90, flush=True)
for i, (cmd, expected) in enumerate(CASES, 1):
    _turn_tool_calls.clear()
    _turn_tools_exec.clear()
    t0 = time.time()
    try:
        reply = agent.run_content(cmd)
        content = (getattr(reply, "content", "") or "").replace("\n", " ")[:90]
        err = getattr(reply, "error", None)
    except Exception as e:
        content = f"EXCEPTION: {type(e).__name__}: {e}"
        err = "exc"
    dt = time.time() - t0
    tools = ",".join(_turn_tool_calls) if _turn_tool_calls else "(NINGUNO)"
    execd = ",".join(_turn_tools_exec) if _turn_tools_exec else "(NINGUNO)"
    print(f"[{i}] {cmd!r}", flush=True)
    print(f"    esperado~={expected} | tool_calls={tools} | exec={execd} | dt={dt:.2f}s | err={err}", flush=True)
    print(f"    reply: {content!r}", flush=True)
    print("-" * 90, flush=True)
