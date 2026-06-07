"""Barre comandos de acción variados en EN/PT/FR/DE/IT y marca cuáles leakean ES.
Identifica qué short-circuits faltan cablear. run_content seguro (exec mockeado)."""
import sys, os, re
sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")  # no contaminar la DB de Jarvis en pruebas
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)
from gemma4_agent.tools_pkg.tools import ToolRegistry
ToolRegistry.execute = lambda self,n,a: {"ok":True,"status":"dispatched","verified":None,"_eval_mock":True}
from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent(); agent.run_content("hola")
# comandos de acción variados por idioma (open/close/volume/screenshot/media/window/url)
CASES = [
 ("en","open spotify"),("en","close chrome"),("en","set volume to 30"),("en","take a screenshot"),
 ("en","mute the sound"),("en","play music"),("en","open youtube.com"),
 ("pt","abre o spotify"),("pt","fecha o chrome"),("pt","coloca o volume em 30"),("pt","tira um print"),
 ("fr","ouvre spotify"),("fr","ferme chrome"),("fr","mets le volume à 30"),("fr","fais une capture"),
 ("de","öffne spotify"),("de","schließe chrome"),("de","stell die lautstärke auf 30"),
 ("it","apri spotify"),("it","chiudi chrome"),("it","imposta il volume a 30"),
]
_es = re.compile(r"^\s*(listo|abrí|cerré|saqué|silenci|subí|bajé|puse|navegué|entré|abrir|reproduc)", re.I)
print("\n=== barrido acción×idioma (LEAK = reply NO en el idioma del user) ===", flush=True)
# Detección por py3langid (no por prefijo "Listo," que daba falsos positivos:
# "Listo, fechei o Chrome" ES portugués correcto). El leak real = el reply NO
# está en el idioma esperado.
try:
    import py3langid as _lid
    _lid.set_languages(["en","es","pt","fr","de","it"])
    def _rlang(s): return _lid.classify(s)[0] if s.strip() else "es"
except Exception:
    def _rlang(s): return "es"
leaks=0
for lang,msg in CASES:
    try: agent.history.clear()
    except Exception: pass
    r=agent.run_content(msg); rep=(getattr(r,"content","") or "")
    rl=_rlang(rep)
    # leak si el reply no está en el idioma esperado (con tolerancia: replies muy
    # cortos pueden mis-clasificar; marcamos leak solo si py3langid difiere claramente)
    leak = (rl != lang)
    leaks+=leak
    print(f"  [{lang}] {'LEAK('+rl+')' if leak else 'ok    '} {msg!r} -> {rep[:55]!r}", flush=True)
print(f"\nLEAKS (reply≠idioma user): {leaks}/{len(CASES)}", flush=True)
