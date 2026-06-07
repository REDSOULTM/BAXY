"""Batería COMPREHENSIVA de computer-use (Fase A: routing + plan, exec físico
MOCKEADO). Cubre todas las categorías de accesibilidad/orquestación con varios
fraseos. Imprime la tool-chain + plan + reply por caso, agrupado, para analizar
qué rutea bien y qué hay que arreglar. CERO SendInput, cero side-effects reales."""
from __future__ import annotations
import os, sys, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")  # no contaminar la DB de Jarvis en pruebas
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)
from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.computer_use_pkg import computer_use as cu
from gemma4_agent.agent_core.agent import Gemma4Agent

cap = {"dispatch": [], "plans": []}
_real = ToolRegistry.execute
ToolRegistry.execute = lambda self, n, a: (cap["dispatch"].append((n, dict(a or {}))) or
    (_real(self, n, a) if n == "computer_use" else {"ok": True, "_mock": True}))
cu.PlanExecutor.execute = lambda self, plan, *a, **k: (cap["plans"].append(plan) or
    {"ok": True, "verified": True, "steps": [{"op": p.get("op"), "arg": p.get("arg")} for p in (plan or [])]})
# simular apps abiertas para que el routing de "tipeá/clickeá en X" trate X como ventana real
_OPEN = {"notepad", "bloc", "bloque", "notas", "word", "calculadora", "calc",
         "spotify", "discord", "whatsapp", "explorador", "youtube", "chrome",
         "navegador", "claude", "code", "canvas", "uniej"}
Gemma4Agent._window_title_in_text = lambda self, t: ("App - " + t) if (
    {w for w in re.findall(r"\w+", (t or "").lower()) if len(w) >= 4} & _OPEN) else None

def run(msg):
    a = Gemma4Agent(); cap["dispatch"].clear(); cap["plans"].clear()
    r = a.run_content(msg)
    return list(cap["dispatch"]), list(cap["plans"]), (getattr(r, "content", "") or "").strip()

CATEGORIES = {
    "TYPE_IN_APP (-> cu plan focus+type)": [
        "escribí hola mundo en el bloc de notas", "escribile gracias a Word",
        "en notepad poné mi nombre", "tipeá la fecha en el word",
        "write hello in notepad", "dictá un mensaje en el bloc de notas",
    ],
    "CLICK_ELEMENT (-> cu plan click)": [
        "en el Word hacé click en Guardar", "apretá el botón Aceptar",
        "clickeá en Archivo en el bloc de notas", "hacé click en Enviar en whatsapp",
    ],
    "OPEN_APP (-> app.open)": [
        "abrí la calculadora", "abrí Spotify", "lanzá el bloc de notas",
        "abrime Discord", "abrí el explorador de archivos",
    ],
    "CHAIN (-> multi-intent)": [
        "abrí la calculadora y escribí 5+5", "abrí el bloc de notas y poné hola",
        "instalá VLC y abrilo", "abrí Spotify y poné rock",
        "sacá un screenshot y abrí la calculadora",
    ],
    "INSTALL (-> package/steam)": [
        "instalá Discord", "bajate VLC", "instalá Terraria de Steam", "descargá OBS",
    ],
    "SCREENSHOT (-> vision/screenshot)": [
        "sacá una captura de pantalla", "tomá un screenshot",
        "mostrame qué hay en la pantalla",
    ],
    "WEB_NAV (-> browser/web)": [
        "andá a la página de pivigames", "buscá recetas de pizza", "abrí youtube",
        "entrá a gmail", "buscá el clima de hoy",
    ],
    "INAPP_GOAL (-> cu goal / discord cap)": [
        "abrí Discord y andá al canal general", "en Discord entrá al canal de música",
        "abrí WhatsApp y mandale a Letras hola",
    ],
    "SYSTEM (-> audio/system/device)": [
        "subí el volumen", "bajá el brillo", "conectate al wifi de casa",
        "silenciá el audio", "poné el volumen al 50",
    ],
    "MISSION (-> cu goal multi-paso)": [
        "andá al portal de la UNIEJ, entrá a Canvas y mostrame las tareas",
        "abrí el navegador, entrá a youtube y buscá lofi",
    ],
}

for cat, phrases in CATEGORIES.items():
    print(f"\n##### {cat} #####", flush=True)
    for u in phrases:
        disp, plans, rep = run(u)
        tools = " -> ".join(n for n, _ in disp) or "(nada)"
        ops = [(p.get("op"), str(p.get("arg"))[:24]) for pl in plans for p in (pl or [])]
        line = f"  {u!r:52} | {tools}"
        print(line, flush=True)
        if ops:
            print(f"       plan={ops}", flush=True)
        if not plans and not disp:
            print(f"       reply={rep[:80]!r}", flush=True)
print("\n[done]", flush=True)
