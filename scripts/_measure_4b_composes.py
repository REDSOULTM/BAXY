"""¿El 4B compone computer-use SOLO (sin macros), si le damos bien las primitivas?

Decide si el rediseño universal es BORRAR los macros (_try_in_app_nav/_message) o si
hacen falta. Macros OFF (GEMMA4_INAPP_NAV=0); la desambiguación por estado del SO
sigue (inyecta uia/gui/window). Verifica por ESTADO DEL SO (título de ventana), NO
por el texto del modelo. 1 sesión multi-turno (flujo real).

GATE (definido ANTES de medir): el 4B compone bien >=7/10 -> los macros sobran
(borrar, rediseño = simplificar). <7/10 -> los macros o un mini-planner se
justifican, pero como UNA capa universal, no N macros por intención.

NO envía mensajes (solo navega/abre — verificable por título sin efectos en terceros).
"""
import os, sys, time, json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["GEMMA4_INAPP_NAV"] = "0"          # MACROS OFF -> el 4B compone solo
os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")

import win32gui, win32con

def disc_title():
    o = [""]
    def c(h, _):
        t = win32gui.GetWindowText(h)
        if "Discord" in t and not t.startswith("Discord Overlay"):
            o[0] = t
        return True
    win32gui.EnumWindows(c, None)
    return o[0]

def opera_title():
    o = [""]
    def c(h, _):
        t = win32gui.GetWindowText(h)
        if "Opera" in t:
            o[0] = t
        return True
    win32gui.EnumWindows(c, None)
    return o[0]

def restore_min(name):
    hd = []
    def c(h, _):
        t = win32gui.GetWindowText(h)
        if name in t and not t.startswith("Discord Overlay") and win32gui.IsWindowVisible(h):
            hd.append(h)
        return True
    win32gui.EnumWindows(c, None)
    if hd:
        win32gui.ShowWindow(hd[0], win32con.SW_RESTORE)

def build_agent():
    from gemma4_agent.agent import Gemma4Agent
    from gemma4_agent.config import AgentConfig
    return Gemma4Agent(AgentConfig.from_env())

# (comando, verificador(title_fn)->bool tras correr). Misiones de nav-en-app que
# ANTES hacían los macros. Si el 4B las hace solo, los macros sobran.
def v_title_has(title_fn, word):
    return lambda: word.lower() in (title_fn() or "").lower()

CASES = [
    ("andá a discord al chat de cbayeah",        v_title_has(disc_title, "cbayeah")),
    ("entrá a discord al chat de GordoFriki",     v_title_has(disc_title, "gordofriki")),
    ("en discord abrí el chat de juanpi",         v_title_has(disc_title, "juanpi")),
    ("andá a discord al chat de pierosky",        v_title_has(disc_title, "pierosky")),
    ("entrá a discord a Migue_STg",               v_title_has(disc_title, "migue")),
    ("andá a discord al chat de cbayeah",         v_title_has(disc_title, "cbayeah")),
    ("entrá a opera y andá a python.org",         v_title_has(opera_title, "python")),
    ("en opera entrá a github.com",               v_title_has(opera_title, "github")),
    ("andá a opera y entrá a wikipedia.org",      v_title_has(opera_title, "wikipedia")),
    ("entrá a discord al chat de ShooterCOCK",    v_title_has(disc_title, "shooter")),
]

print(f"=== ¿4B compone solo (macros OFF)? x{len(CASES)} ===", flush=True)
print(f"GEMMA4_INAPP_NAV={os.environ.get('GEMMA4_INAPP_NAV')}", flush=True)
restore_min("Discord")
ag = build_agent()
ag.run_text("hola")
results = []
for cmd, verify in CASES:
    seen = []
    def progress(stage, info=None): seen.append((stage, info))
    t = time.time()
    try:
        r = ag.run_text(cmd, progress=progress)
        reply = (getattr(r, "content", None) or "")
        err = getattr(r, "error", None)
    except Exception as exc:
        reply = ""; err = f"EXC {type(exc).__name__}: {exc}"
    dt = time.time() - t
    # qué tools ejecutó (para ver si compuso focus+operar)
    tools_run = [i.get("name") for s, i in seen if s == "tool_start" and isinstance(i, dict)]
    time.sleep(0.8)
    ok = False
    try: ok = verify()
    except Exception: ok = False
    results.append({"cmd": cmd, "ok": ok, "tools": tools_run,
                    "reply": reply.encode("ascii", "replace").decode()[:60],
                    "latency_s": round(dt, 1)})
    print(f"  {'OK ' if ok else 'FAIL'} | tools={tools_run} | {cmd!r} | {reply[:45]!r}", flush=True)

n = sum(1 for r in results if r["ok"])
out = ROOT / "scripts" / "gui_eval" / "_measure_4b_composes_results.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
verdict = "MACROS SOBRAN (borrar)" if n >= 7 else "MACROS/planner JUSTIFICADOS"
print(f"\n>> 4B compone solo: {n}/{len(CASES)}  GATE>=7 -> {verdict}", flush=True)
print("WROTE", out, flush=True)
