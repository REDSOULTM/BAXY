"""Stress EN VIVO para el sprint v22 (b9384 + MAX_TOOLS variable).

Objetivo: ejercitar el regimen donde aparecia el crash CUDA #22527 (prompts
>~13k tokens) con prompts variados y medir, POR TURNO:
  - tamano REAL del prompt enviado al server (hook a LLMClient.chat, passthrough)
  - latencia
  - ok/fail + error
  - #tools y #llamadas al server (planning + forced-retry + pass-2)

A diferencia de _measure_agent_prompt_live.py, este SI llama al server real
(passthrough), asi que puede disparar el crash si sigue presente.

El crash CUDA definitivo se confirma con grep a logs/llama-server.err.log
DESPUES de la corrida (este harness reporta la senial a nivel-agente:
excepciones, replies con error, turnos anormalmente lentos por recovery).

Uso:
  $env:GEMMA4_MAX_SELECTED_TOOLS=8; $env:GEMMA4_HARD_TOOL_CAP=8
  python scripts/_stress_v22.py
"""
import os
import sys
import json
import time
import statistics
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra import llm_client

CHARS_PER_TOK = 3.6
_calls = []  # mediciones de chat() del turno actual

orig_chat = llm_client.LLMClient.chat


def wrapped_chat(self, messages, **kw):
    """Mide el prompt real y HACE PASSTHROUGH al server (no corta)."""
    try:
        system = next((m for m in messages if m.get("role") == "system"), None)
        sys_chars = len(system["content"]) if system and system.get("content") else 0
        hist_chars = sum(
            len(json.dumps(m, ensure_ascii=False))
            for m in messages
            if m.get("role") != "system"
        )
        tools_payload = kw.get("tools") or []
        tools_chars = len(json.dumps(tools_payload, ensure_ascii=False))
        total_toks = int((sys_chars + hist_chars + tools_chars) / CHARS_PER_TOK)
        _calls.append({"tools": len(tools_payload), "toks": total_toks})
    except Exception as exc:  # medicion nunca debe romper la corrida
        _calls.append({"tools": -1, "toks": -1, "measure_err": str(exc)})
    return orig_chat(self, messages, **kw)


llm_client.LLMClient.chat = wrapped_chat

print(
    f"[stress] MAX_SELECTED={os.environ.get('GEMMA4_MAX_SELECTED_TOOLS','(def5)')} "
    f"HARD_CAP={os.environ.get('GEMMA4_HARD_TOOL_CAP','(def5)')} | cargando agente...",
    flush=True,
)
agent = Gemma4Agent()

# Mensajes largos para forzar prompts grandes por si solos.
_SENT = (
    "Te cuento la situacion con detalle para que tengas todo el contexto: "
    "ayer estuve organizando los archivos del trabajo y quedaron varias cosas "
    "a medio terminar que necesito retomar hoy sin perder el hilo de nada. "
)
LONG_MED = "Resumime esto y decime por donde arranco: " + (_SENT * 28)   # ~3.9k chars
LONG_BIG = "Necesito que proceses todo este texto largo: " + (_SENT * 55)  # ~7.5k chars

PROMPTS = [
    # --- conversacional corto ---
    ("conv", "Hola, todo bien?"),
    ("conv", "Contame un chiste corto"),
    ("conv", "Jaja gracias, sos un genio"),
    ("conv", "Que opinas de la inteligencia artificial?"),
    # --- info ---
    ("info", "Que dia es hoy?"),
    ("info", "Cuanto es 128 por 47?"),
    ("info", "Quien pinto la Mona Lisa?"),
    ("info", "Cual es la capital de Australia?"),
    ("info", "Cuantos planetas hay en el sistema solar?"),
    ("info", "Explicame que es la fotosintesis en una linea"),
    # --- accion (tool-heavy -> subset grande) ---
    ("tool", "Abri Spotify y pone algo de rock"),
    ("tool", "Subi el volumen al 80 por ciento"),
    ("tool", "Baja el brillo de la pantalla"),
    ("tool", "Busca en Google las noticias de hoy"),
    ("tool", "Abri el bloc de notas"),
    ("tool", "Mandale un mensaje a mi hermano por WhatsApp que llego tarde"),
    ("tool", "Saca una captura de pantalla"),
    ("tool", "Conectate al wifi de casa"),
    ("tool", "Pone una alarma para las 7 de la maniana"),
    ("tool", "Abri el navegador y anda a YouTube"),
    ("tool", "Pausa la musica"),
    ("tool", "Abri la calculadora"),
    ("tool", "Apaga la musica y baja el brillo"),
    ("tool", "Reproduci el ultimo video que vi"),
    # --- deicticos cortos (apoyan en historial) ---
    ("deic", "dale"),
    ("deic", "si, ese"),
    ("deic", "mas fuerte"),
    ("deic", "y ahora que?"),
    ("deic", "el otro no"),
    # --- mensajes largos (fuerzan prompt grande solos) ---
    ("long", LONG_MED),
    ("long", LONG_BIG),
    ("long", "Sobre todo lo que te conte recien, " + (_SENT * 35)),
    # --- mas accion para llegar a 30+ ---
    ("tool", "Cerra la ventana activa"),
    ("tool", "Sube un poco mas el volumen"),
    ("tool", "Abri la configuracion de Windows"),
    ("tool", "Minimiza todas las ventanas"),
    ("info", "Decime el clima en Cordoba"),
]

results = []
t_start = time.time()
for i, (kind, p) in enumerate(PROMPTS, 1):
    _calls.clear()
    t0 = time.time()
    err = None
    ok = False
    snip = ""
    try:
        reply = agent.run_content(p)
        content = getattr(reply, "content", "") or ""
        err_field = getattr(reply, "error", None)
        ok = bool(content.strip()) and not err_field
        snip = content[:70].replace("\n", " ")
        err = err_field
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)[:120]}"
        traceback.print_exc()
    dt = time.time() - t0
    max_toks = max((c["toks"] for c in _calls), default=0)
    max_tools = max((c["tools"] for c in _calls), default=0)
    n_calls = len(_calls)
    results.append({
        "i": i, "kind": kind, "p": p[:38], "ok": ok, "dt": dt,
        "max_toks": max_toks, "max_tools": max_tools, "n_calls": n_calls, "err": err,
    })
    flag = "OK  " if ok else "FAIL"
    errs = f" ERR={err}" if err else ""
    print(
        f"[stress] {i:2d}/{len(PROMPTS)} [{kind}] {flag} dt={dt:6.2f}s "
        f"toks={max_toks:6,d} tools={max_tools} calls={n_calls}{errs} :: {p[:40]!r}",
        flush=True,
    )

total = time.time() - t_start
ok_n = sum(1 for r in results if r["ok"])
ge13 = sum(1 for r in results if r["max_toks"] >= 13000)
ge14 = sum(1 for r in results if r["max_toks"] >= 14000)
maxtok = max((r["max_toks"] for r in results), default=0)
exc_n = sum(1 for r in results if r["err"])
dts = sorted(r["dt"] for r in results)

print("=" * 92)
print(f"[stress] DONE turns={len(results)} ok={ok_n}/{len(results)} total={total:.1f}s")
print(f"[stress] prompts>=13k: {ge13}/{len(results)}  >=14k: {ge14}/{len(results)}  "
      f"max_prompt_toks={maxtok:,}  turns_with_error={exc_n}")
if dts:
    p50 = statistics.median(dts)
    p90 = dts[min(len(dts) - 1, int(len(dts) * 0.9))]
    print(f"[stress] latency p50={p50:.2f}s p90={p90:.2f}s max={max(dts):.2f}s")
print("[stress] turnos con error (si los hay):")
for r in results:
    if r["err"]:
        print(f"   turn {r['i']} [{r['kind']}] toks={r['max_toks']:,} err={r['err']}")
