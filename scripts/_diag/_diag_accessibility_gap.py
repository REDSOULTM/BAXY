"""MEDIR EL GAP (accesibilidad) — routing + plan del 4B, con tus frases REALES
(de los traces) + variantes acentuadas/STT. Ejecución física MOCKEADA (CERO
SendInput, cero apps). Simula apps abiertas (mock _window_title_in_text) para medir
la lógica de routing en el escenario real. Gate: ≥80% accesibilidad -> computer_use
con plan focus_app+type correcto; controles (mensaje/notes/web/audio) NO."""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)
from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.computer_use_pkg import computer_use as cu
from gemma4_agent.agent_core.agent import Gemma4Agent

cap = {"dispatch": [], "plans": []}
_real = ToolRegistry.execute
ToolRegistry.execute = lambda self,n,a: (cap["dispatch"].append((n,dict(a or {}))) or
    (_real(self,n,a) if n=="computer_use" else {"ok":True,"_mock":True}))
cu.PlanExecutor.execute = lambda self,plan,*a,**k: (cap["plans"].append(plan) or
    {"ok":True,"verified":True,"steps":[{"op":p.get("op"),"arg":p.get("arg")} for p in (plan or [])]})
_OPEN = {"notepad","bloc","bloque","notas","claude","claudio","code","discord","word","calculadora","spotify"}
Gemma4Agent._window_title_in_text = lambda self,t: ("App - "+t) if (
    {w for w in __import__("re").findall(r"\w+",(t or "").lower()) if len(w)>=4} & _OPEN) else None

def run(msg):
    a = Gemma4Agent(); cap["dispatch"].clear(); cap["plans"].clear()
    r = a.run_content(msg)
    return list(cap["dispatch"]), list(cap["plans"]), (getattr(r,"content","") or "").strip()

# TUS FRASES REALES (de traces) + variantes por voz/acento/idioma/app
ACCESS = [
    "Abre el bloque de notas y escríbele Hola Mundo",     # <- tu test que falló
    "en Claudio Code escribe quién eres",                  # <- STT real (Claudio)
    "escribí sigue en claude code", "escribile sigue a claude code",
    "escríbele hola en notepad", "en notepad escribí mi nombre",
    "poné reunión a las 5 en el bloc de notas", "type hello world in notepad",
    "andá a Claude Code y escribí continuá", "escribí gracias en Discord",
    "abrí la calculadora y escribí 5+5", "sacá un screenshot",
    # variantes nuevas (robustez)
    "tipeá hola en el bloc de notas", "escribe mi nombre en notepad",
    "digitá 1234 en la calculadora", "poné la fecha en el word",
    "write hello world in notepad", "andá a Word y escribí mi nombre",
    "abrí el bloc de notas y poné hola", "tomá una captura de pantalla",
]
CONTROL = ["mandale a juan que ya voy", "anotá comprar pan en mi lista",
    "subí el volumen", "buscá noticias de hoy", "qué hora es", "abrí spotify",
    "respondele a mama que sí", "reproducí rock en spotify",
    "en spotify buscá rock", "recordame comprar pan", "qué tengo en la agenda"]

print("\n##### ACCESIBILIDAD (gate ≥80% -> cu con plan correcto) #####")
ok=0; okplan=0
for u in ACCESS:
    disp,plans,rep = run(u)
    # cu via dispatch (goal-only) O via plan capturado (determinista, llama handler directo)
    hit = any(n=="computer_use" for n,_ in disp) or bool(plans); ok+=hit
    ops=[(p.get("op"),p.get("arg")) for pl in plans for p in (pl or [])]
    has_type = any(o[0] in ("type","fill_field") for o in ops)
    has_focus = any(o[0] in ("focus_app","open_url","open_chat") for o in ops)
    good = hit and has_type and has_focus; okplan+=good
    print(f"  {'✓' if good else ('cu' if hit else 'XX')} {u!r:48}")
    if ops: print(f"       plan={ops}")
    else:   print(f"       ruta={' -> '.join(n for n,_ in disp) or 'nada'} reply={rep[:60]!r}")
print(f"  => {ok}/{len(ACCESS)} a cu ; {okplan}/{len(ACCESS)} con plan focus+type correcto")

print("\n##### CONTROL (NO deben ir a cu) #####")
cok=0
for u in CONTROL:
    disp,_,_ = run(u); bad=any(n=="computer_use" for n,_ in disp); cok+=(not bad)
    print(f"  {'XX!' if bad else 'OK'} {u!r:38} -> {' -> '.join(n for n,_ in disp) or 'nada'}")
print(f"  => {cok}/{len(CONTROL)} correctamente NO a cu")
