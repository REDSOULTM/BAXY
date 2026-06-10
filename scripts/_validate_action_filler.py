"""Validación EN VIVO del confirm filler (action_filler + _voice_action_filler).

Real LLM (server FA-off, perfil vram4) + real agente + real router. El sink es
FALSO: registra (t_relativo, texto) por feed — SIN audio, SIN SendInput (seguro).

GATES (definidos antes de correr):
  G1 cobertura : el filler se voca en TODOS los turnos de acción (no-early) y
                 ANTES de que el reply esté listo (t_filler << t_reply).
  G2 honestidad: ningún filler contradice el resultado. Intent-aware ("Abriendo
                 X") solo si el turno realmente intenta abrir X (se imprimen los
                 tool events para verificarlo); genérico no promete nada.
  G3 reply real: el reply final sale igual (no vacío, sin error) — el filler es
                 un preámbulo, no un reemplazo.
  G4 interplay : con GEMMA4_STREAM_TTS=1 el filler precede al stream del reply
                 sin double-speak (feeds = filler + prosa, en ese orden).

Acciones benignas (abrir apps inofensivas / minimizar; NO cambia volumen ni
registro). Correr:  python scripts/_validate_action_filler.py
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
os.environ.setdefault("GEMMA4_DIAG", "1")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
mgr = get_shared_manager()
print(f"[boot] perfil={prof.name}; arrancando llama-server...", flush=True)
_t = time.time()
st = mgr.start(prof, wait_health=True, timeout_s=120)
print(f"[boot] status={st!r} en {time.time()-_t:.1f}s", flush=True)

from gemma4_agent.agent_core.agent import Gemma4Agent


class Sink:
    def __init__(self):
        self.calls = []
        self._t0 = None

    def arm(self):
        self.calls = []
        self._t0 = time.monotonic()

    def __call__(self, text):
        self.calls.append((time.monotonic() - (self._t0 or time.monotonic()), text))
        return len(text)


sink = Sink()
print("[boot] cargando agente...", flush=True)
agent = Gemma4Agent()

# (comando, filler esperado) — "generic" = del banco genérico; "none" = sin
# filler (early-reply, modo info/charla, o sin tools de acción).
# MEDIDO (corridas 1-2): (a) los "abrí <app/sitio resoluble>" NO llegan al
# filler — el app-open net los resuelve en decide (~1s, early_reply, no hay
# silencio que enmascarar); (b) en charla el router puede ofrecer tools pero el
# modo es fast_info -> sin filler (gate por modo *_action); (c) intent-aware
# ("Abriendo X") queda OPT-IN (GEMMA4_FILLER_INTENT): el subset de opens que
# llega al LLM es el que el net NO resolvió y el filler contradecía el fallo
# (live: "Abriendo jitomatador." -> "No llegué a ejecutar ninguna acción").
CASES = [
    ("qué linda mañana", "none"),        # charla -> modo info, sin filler
    ("abrí el bloc de notas", "none"),   # app-open net -> early ~1s, sin filler
    ("minimizá la ventana", "generic"),  # acción por LLM -> genérico
    ("maximizá la ventana", "generic"),  # 2º genérico: valida rotación (texto distinto)
    # open que el net NO resuelve (app inexistente) -> genérico (intent OFF):
    # el genérico NO contradice el fallo del turno (G2).
    ("abrí jitomatador", "generic"),
]

_GENERIC_MARKERS = ("segundo", "voy con eso", "Enseguida", "momento", "ahí va",
                    "sec", "On it", "moment", "check that", "Right away")


def classify(feed_text: str) -> str:
    if feed_text.startswith(("Abriendo ", "Opening ")):
        return "intent"
    if any(m in feed_text for m in _GENERIC_MARKERS):
        return "generic"
    return f"other:{feed_text[:30]!r}"


def run(cmd: str):
    sink.arm()
    t0 = time.monotonic()
    try:
        reply = agent.run_content(cmd, tts_sink=sink)
        err = getattr(reply, "error", None)
    except Exception as e:  # noqa: BLE001
        return None, time.monotonic() - t0, f"EXC {type(e).__name__}: {e}"
    return reply, time.monotonic() - t0, err


print("[warm] turno de calentamiento (descartado)...", flush=True)
try:
    run("abrí la calculadora")
except Exception:
    pass

print("=" * 96, flush=True)
g_fail = []
generic_fillers = []
for cmd, expect in CASES:
    reply, dt, err = run(cmd)
    events = getattr(reply, "tool_events", []) or [] if reply else []
    content = ((getattr(reply, "content", "") or "") if reply else "").replace("\n", " ")
    feeds = list(sink.calls)
    f_t, f_text = (feeds[0][0], feeds[0][1].strip()) if feeds else (None, "")
    got = classify(f_text) if f_text else "none"
    # tool_events trae dataclass ToolEvent (name/args/result) -> getattr.
    ev_desc = [f"{getattr(e, 'name', e)}:{getattr(e, 'args', {})}" for e in events][:3]
    ok = True
    if expect == "none":
        ok = got == "none"
    else:
        ok = (got == expect) and f_t is not None and f_t < dt * 0.5
    ok = ok and bool(content) and not err
    if got == "generic":
        generic_fillers.append(f_text)
    if not ok:
        g_fail.append(cmd)
    print(f"[{'OK ' if ok else 'FAIL'}] {cmd!r}", flush=True)
    print(f"       filler={f_text!r} ({got}, esperado {expect})"
          f"  t_filler={f'{f_t:.2f}s' if f_t is not None else '—'}  t_reply={dt:.2f}s", flush=True)
    print(f"       events={ev_desc}", flush=True)
    print(f"       reply={content[:110]!r}  err={err}", flush=True)
    print("-" * 96, flush=True)

# Rotación: dos genéricos seguidos deben variar (contador de instancia, sin random).
if len(generic_fillers) >= 2 and len(set(generic_fillers)) < 2:
    g_fail.append("rotacion_generic")
    print(f"[FAIL] rotación: genéricos repetidos {generic_fillers!r}", flush=True)

# G4: interplay con streaming TTS — turno de acción NO-early (window va por el
# LLM): el filler debe preceder al stream del reply, sin double-speak.
os.environ["GEMMA4_STREAM_TTS"] = "1"
try:
    reply, dt, err = run("minimizá la ventana otra vez")
    feeds = list(sink.calls)
    first = feeds[0][1].strip() if feeds else ""
    rest = "".join(t for _, t in feeds[1:])
    inter_ok = classify(first) in ("intent", "generic") and not err
    print(f"[{'OK ' if inter_ok else 'FAIL'}] interplay STREAM_TTS=1: filler={first!r} "
          f"luego stream {len(feeds)-1} feeds: {rest[:80]!r}", flush=True)
    print(f"       reply={((getattr(reply, 'content', '') or '') if reply else '')[:110]!r}", flush=True)
    if not inter_ok:
        g_fail.append("interplay_stream_tts")
finally:
    os.environ.pop("GEMMA4_STREAM_TTS", None)

print("=" * 96, flush=True)
print(f"[VEREDICTO] {'TODO OK' if not g_fail else 'FALLAS: ' + ', '.join(g_fail)}", flush=True)
print("[nota] G2 (honestidad intent-aware) se verifica leyendo events vs filler arriba.", flush=True)
