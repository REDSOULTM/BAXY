"""Valida que el fix E (vocativo no vuelca identidad) sea MULTILINGÜE: ser llamado
por nombre para una acción en FR/EN/DE/PT NO debe disparar "soy un modelo de
lenguaje…". LLM real + tools mockeadas (seguro)."""
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
print("[boot] llama-server...", flush=True)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
for _n in list(agent.tools._impls.keys()):
    agent.tools._impls[_n] = (lambda n: (lambda a: {"ok": True, "tool": n, "mocked": True, "verified": True}))(_n)

DUMP = ["modelo de lenguaje", "deepmind", "soy gemma", "large language model", "language model",
        "modèle de langage", "sprachmodell", "modelo de linguagem", "developed by google",
        "développé par google", "entwickelt von google", "desenvolvido pelo google"]

# (frase, idioma) — vocativo + acción; NINGUNO debe auto-presentarse
CASES = [
    ("Gemma, open Steam", "EN"),
    ("Gemma, mets une chanson sur Spotify", "FR"),
    ("Gemma, spiel ein Lied auf Spotify", "DE"),
    ("Gemma, abre o Steam", "PT"),
    ("Hey Gemma, what time is it?", "EN-q"),
]

print("=" * 78, flush=True)
fails = 0
for text, lang in CASES:
    try:
        r = agent.run_content(text)
        reply = (getattr(r, "content", "") or "").replace("\n", " ")
    except Exception as e:
        print(f"  <EXC {type(e).__name__}: {e}>", flush=True); fails += 1; continue
    low = reply.lower()
    dumped = any(k in low for k in DUMP)
    if dumped:
        fails += 1
    print(f"[{'FALLA' if dumped else 'OK  '}] {lang:6} {text!r}", flush=True)
    print(f"        identidad_volcada={dumped}  reply={reply[:110]!r}", flush=True)
print("=" * 78, flush=True)
print(f"[VEREDICTO E-multi] {'OK (ningun idioma vuelca identidad)' if fails == 0 else f'FALLA ({fails})'}", flush=True)
