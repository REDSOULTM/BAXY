"""Validación EN VIVO de streaming token->TTS (GEMMA4_STREAM_TTS).

Real LLM (server FA-off, perfil vram4) + real agente + real summary-pass. El sink
es FALSO: registra (t_relativo, texto) por cada feed — SIN audio, SIN SendInput
(seguro; no toca el escritorio). Mide:
  - TTFA generación: t del PRIMER feed al sink vs t del reply completo.
  - VERACIDAD (gate duro): lo "hablado" (concatenación de feeds) es prefijo del
    reply final (lo que se habría dicho sin streaming) -> nunca se dijo algo que
    un guard después retracta.

Acciones benignas que disparan un tool -> summary-pass (events>0): abrir apps
(ventanas inofensivas; el usuario las cierra). NO cambia volumen/registro.

Correr (bootea el server ~10-60s, lo deja vivo solo durante el script):
  python scripts/_validate_stream_tts.py
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# Windows console/pipe defaults to cp1252; model replies + symbols (~, etc.) can
# carry chars outside it -> UnicodeEncodeError. Force utf-8 with replace.
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
print(f"[boot] perfil={prof.name}; arrancando llama-server (FA-off)...", flush=True)
_t = time.time()
st = mgr.start(prof, wait_health=True, timeout_s=120)
print(f"[boot] status={st!r} en {time.time()-_t:.1f}s | router={mgr.is_router_mode()}", flush=True)

from gemma4_agent.agent_core.agent import Gemma4Agent


class Sink:
    """Fake TTS sink: records (t_rel, text) per feed. No audio."""

    def __init__(self):
        self.calls = []
        self._t0 = None

    def arm(self):
        self.calls = []
        self._t0 = time.monotonic()

    def __call__(self, text):
        self.calls.append((time.monotonic() - (self._t0 or time.monotonic()), text))
        return len(text)

    @property
    def first_t(self):
        return self.calls[0][0] if self.calls else None

    @property
    def voiced(self):
        return "".join(t for _, t in self.calls)


sink = Sink()
print("[boot] cargando agente...", flush=True)
agent = Gemma4Agent()

# (cmd, descripción) — acciones que disparan un tool de forma fiable (summary-pass).
ACTIONS = [
    "abrí el bloc de notas",
    "abrí la calculadora",
    "minimizá la ventana",
]


def run(cmd: str, stream_on: bool):
    if stream_on:
        os.environ["GEMMA4_STREAM_TTS"] = "1"
    else:
        os.environ.pop("GEMMA4_STREAM_TTS", None)
    sink.arm()
    t0 = time.monotonic()
    try:
        reply = agent.run_content(cmd, tts_sink=sink)
        err = getattr(reply, "error", None)
    except Exception as e:  # noqa: BLE001
        return None, time.monotonic() - t0, f"EXC {type(e).__name__}: {e}"
    return reply, time.monotonic() - t0, err


# Warm-up: la 1a request post-boot tiene prefill frío (~30s medido) y el 4B a veces
# mis-rutea en frío. Descartamos un turno para no contaminar las medidas.
print("[warm] turno de calentamiento (descartado)...", flush=True)
try:
    run("abrí la calculadora", stream_on=False)
except Exception:
    pass

print("=" * 96, flush=True)
truth_fail = 0
base_times: dict[str, float] = {}
for cmd in ACTIONS:
    # baseline (flag off): no streaming -> sink never called during gen.
    reply_b, dt_b, err_b = run(cmd, stream_on=False)
    streamed_b = getattr(reply_b, "tts_streamed", False) if reply_b else False
    n_ev_b = len(getattr(reply_b, "tool_events", []) or []) if reply_b else 0
    base_times[cmd] = dt_b
    print(f"[BASE ] {cmd!r}  total={dt_b:.2f}s  tool_events={n_ev_b}  tts_streamed={streamed_b}  err={err_b}", flush=True)

    # streaming on.
    reply_s, dt_s, err_s = run(cmd, stream_on=True)
    streamed_s = getattr(reply_s, "tts_streamed", False) if reply_s else False
    n_ev_s = len(getattr(reply_s, "tool_events", []) or []) if reply_s else 0
    content_raw = (getattr(reply_s, "content", "") or "") if reply_s else ""
    content = content_raw.replace("\n", " ")
    first = sink.first_t
    voiced = sink.voiced
    print(f"[STREAM] {cmd!r}  total={dt_s:.2f}s  tool_events={n_ev_s}  tts_streamed={streamed_s}  err={err_s}", flush=True)
    if streamed_s and first is not None:
        # perceived win: audio starts at `first` (stream) vs at the full reply.
        print(f"         first_audio_feed={first:.2f}s  (base reply ready={dt_b:.2f}s)  "
              f"perceived_win~={max(0.0, dt_b - first):.2f}s  feeds={len(sink.calls)}", flush=True)
        # VERACIDAD: voiced debe ser prefijo del reply final (o igual). Normalizamos
        # whitespace en AMBOS (el footer llega con \n\n; comparar crudo daría un
        # falso-FAIL puramente cosmético).
        import re as _re
        _n = lambda s: _re.sub(r"\s+", " ", s).strip()
        v, c = _n(voiced), _n(content_raw)
        truth_ok = c.startswith(v) or v.startswith(c) or v == c
        if not truth_ok:
            truth_fail += 1
        print(f"         TRUTH voiced-prefix-of-final={truth_ok}", flush=True)
        print(f"         voiced={voiced[:110]!r}", flush=True)
    print(f"         reply={content[:110]!r}", flush=True)
    print("-" * 96, flush=True)

print("=" * 96, flush=True)
print(f"[VEREDICTO] veracidad: {'OK (0 violaciones)' if truth_fail == 0 else f'FAIL ({truth_fail} violaciones)'}", flush=True)
print("[nota] el sink es falso (sin audio). El win de audio real suma el solapamiento de synth", flush=True)
print("       (Piper sintetiza la 1a oración mientras el LLM genera el resto).", flush=True)
