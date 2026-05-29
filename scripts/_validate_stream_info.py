"""Validación EN VIVO del streaming de turnos INFO (GEMMA4_STREAM_TTS, item 2).

Turnos INFO (preguntas, fast_info, sin tool) se generan en UNA pasada (sin la espera
de pass-1+execute), así que streamear arranca el audio antes. PERO en turnos sin-tool
los guards de claim PUEDEN disparar -> _chat_streaming corre los detectores REALES
por-incremento y ABORTA antes de hablar algo que un guard reemplazaría.

Sink FALSO (registra t+texto, sin audio, sin SendInput). Mide: ¿streameó?, TTFA
generación (1er feed) vs reply completo, y VERACIDAD (voiced prefijo del final).
Sin efectos colaterales (solo preguntas).

  python scripts/_validate_stream_info.py
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
print(f"[boot] perfil={prof.name}; server...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120)

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

    @property
    def first_t(self):
        return self.calls[0][0] if self.calls else None

    @property
    def voiced(self):
        return "".join(t for _, t in self.calls)


sink = Sink()
print("[boot] agente...", flush=True)
agent = Gemma4Agent()
agent.run_content("hola")  # warm

QUESTIONS = [
    "qué es la fotosíntesis",
    "cuál es la capital de Francia",
    "explicame brevemente qué es Python",
    "por qué el cielo es azul",
]


def run(cmd, stream_on):
    if stream_on:
        os.environ["GEMMA4_STREAM_TTS"] = "1"
    else:
        os.environ.pop("GEMMA4_STREAM_TTS", None)
    try:
        agent.history.clear()
    except Exception:
        pass
    sink.arm()
    t0 = time.monotonic()
    reply = agent.run_content(cmd, tts_sink=sink)
    return reply, time.monotonic() - t0


import re as _re
_n = lambda s: _re.sub(r"\s+", " ", s).strip()

print("=" * 96, flush=True)
truth_fail = 0
streamed_n = 0
for q in QUESTIONS:
    reply_b, dt_b = run(q, False)
    n_ev_b = len(getattr(reply_b, "tool_events", []) or []) if reply_b else 0
    reply_s, dt_s = run(q, True)
    streamed = getattr(reply_s, "tts_streamed", False) if reply_s else False
    n_ev_s = len(getattr(reply_s, "tool_events", []) or []) if reply_s else 0
    content = (getattr(reply_s, "content", "") or "") if reply_s else ""
    first = sink.first_t
    voiced = sink.voiced
    print(f"[INFO] {q!r}", flush=True)
    print(f"   base_reply_ready={dt_b:.2f}s (events={n_ev_b}) | stream tts_streamed={streamed} "
          f"events={n_ev_s} first_audio={('%.2f' % first) if first is not None else None}s", flush=True)
    if streamed and first is not None:
        streamed_n += 1
        print(f"   perceived_win~={max(0.0, dt_b - first):.2f}s  feeds={len(sink.calls)}", flush=True)
        v, c = _n(voiced), _n(content)
        ok = c.startswith(v) or v.startswith(c) or v == c
        if not ok:
            truth_fail += 1
        print(f"   TRUTH voiced-prefix-of-final={ok}", flush=True)
    print(f"   reply={_n(content)[:120]!r}", flush=True)
    print("-" * 96, flush=True)
print("=" * 96, flush=True)
print(f"[VEREDICTO] streameó {streamed_n}/{len(QUESTIONS)} info-turns | veracidad: "
      f"{'OK (0 violaciones)' if truth_fail == 0 else f'FAIL ({truth_fail})'}", flush=True)
