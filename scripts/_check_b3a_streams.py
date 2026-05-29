"""Check de DEFAULT-ON (sin audio): confirma que B3a streamea una pregunta de INFO
POR DEFECTO (sin env var) vía run_content. Sink FALSO (no reproduce nada), tools
mockeadas. Valida el flip GEMMA4_STREAM_TTS default 0->1 (2026-05-29)."""
import os
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
mgr = get_shared_manager()
print("[boot] arrancando llama-server...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
for _name in list(agent.tools._impls.keys()):
    agent.tools._impls[_name] = (lambda n: (lambda args: {"ok": True, "tool": n, "mocked": True, "verified": True}))(_name)


class FakeSink:
    def __init__(self):
        self.calls = []
        self._t0 = None

    def arm(self):
        self.calls = []
        self._t0 = time.monotonic()

    def __call__(self, text):
        self.calls.append((time.monotonic() - (self._t0 or time.monotonic()), text))
        return len(text)


sink = FakeSink()


def run(prompt):
    # NO seteamos la env var -> confiamos en el DEFAULT (ON tras el flip 2026-05-29).
    os.environ.pop("GEMMA4_STREAM_TTS", None)
    sink.arm()
    t0 = time.monotonic()
    reply = agent.run_content(prompt, tts_sink=sink)
    dt = time.monotonic() - t0
    return reply, dt


print("[warm] descartado...", flush=True)
run("Explicá brevemente qué es el agua.")

print("=" * 76, flush=True)
ok = True
for p in ("Explicá en pocas palabras qué es la fotosíntesis.",
          "Explicá brevemente por qué el cielo se ve azul."):
    reply, dt = run(p)
    streamed = bool(getattr(reply, "tts_streamed", False))
    used = [getattr(e, "name", "?") for e in (getattr(reply, "tool_events", []) or [])]
    first_t = sink.calls[0][0] if sink.calls else None
    voiced = "".join(t for _, t in sink.calls)
    content = (getattr(reply, "content", "") or "").replace("\n", " ")
    print(f"[INFO] {p!r}", flush=True)
    print(f"   tts_streamed={streamed}  feeds={len(sink.calls)}  "
          f"first_feed={first_t if first_t is None else round(first_t,2)}s  "
          f"gen_total={dt:.2f}s  tools={used}", flush=True)
    print(f"   voiced[:90]={voiced[:90]!r}", flush=True)
    print(f"   reply[:90] ={content[:90]!r}", flush=True)
    # veracidad: lo "hablado" debe ser prefijo del reply final
    import re as _re
    _n = lambda s: _re.sub(r"\s+", " ", s).strip()
    v, c = _n(voiced), _n(content)
    truth = (c.startswith(v) or v.startswith(c) or v == c) if v else True
    print(f"   TRUTH voiced-prefix-of-final={truth}", flush=True)
    if not (streamed and len(sink.calls) >= 1 and truth):
        ok = False
    print("-" * 76, flush=True)

print("=" * 76, flush=True)
print(f"[VEREDICTO] streaming-INFO POR DEFECTO (sin env var): {'OK (streamea, veraz)' if ok else 'PROBLEMA (revisar)'}", flush=True)
