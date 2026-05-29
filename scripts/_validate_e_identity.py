"""Valida el fix E (volcado de identidad): un VOCATIVO ("Gema, hacé X") NO debe
disparar "soy un modelo de lenguaje de Google DeepMind…"; pero "quién sos" SÍ debe
presentarse (no sobre-suprimir). LLM real + tools mockeadas (seguro, sin acciones).
"""
import os
import sys
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
print("[boot] arrancando/usando llama-server...", flush=True)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
for _n in list(agent.tools._impls.keys()):
    agent.tools._impls[_n] = (lambda n: (lambda a: {"ok": True, "tool": n, "mocked": True, "verified": True}))(_n)

DUMP = ["modelo de lenguaje", "deepmind", "soy gemma 4", "large language model",
        "desarrollado por google", "modelo de ia", "soy una ia"]

# (prompt, debe_presentarse)
CASES = [
    ("Y Gema, pon una canción de Michael Jackson en Spotify.", False),
    ("Gemma, abrí Steam.", False),
    ("che gemma, qué hora es", False),
    ("Gema, buscá noticias de hoy", False),
    ("quién sos?", True),  # CONTROL: acá SÍ debe presentarse
]

print("=" * 76, flush=True)
fails = 0
for text, should_introduce in CASES:
    try:
        r = agent.run_content(text)
        reply = (getattr(r, "content", "") or "").replace("\n", " ")
    except Exception as e:
        print(f"  <EXC {type(e).__name__}: {e}>", flush=True); fails += 1; continue
    low = reply.lower()
    dumped = any(k in low for k in DUMP)
    ok = (dumped == should_introduce)  # vocativo: no dump; "quién sos": dump esperado
    if not ok:
        fails += 1
    tag = "OK  " if ok else "FALLA"
    exp = "(debe presentarse)" if should_introduce else "(NO debe presentarse)"
    print(f"[{tag}] {exp} {text!r}", flush=True)
    print(f"        identidad_presente={dumped}  reply={reply[:120]!r}", flush=True)
print("=" * 76, flush=True)
print(f"[VEREDICTO E] {'OK (0 fallas)' if fails == 0 else f'FALLA ({fails})'}", flush=True)
