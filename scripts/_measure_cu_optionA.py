"""Mide la OPCIÓN A (ejecutor de planes) end-to-end en apps VARIADAS.

El 4B emite el plan (request_plan), PlanExecutor lo ejecuta, se verifica por ESTADO
DEL SO. 10+ comandos por TIPO de acción, en apps distintas (no solo calc/discord):
navegador (open_url), chat (open_chat), calc (type+keypress), notepad (type),
calc-botones (click), abrir-app (focus_app/launch).

GATE universal: >=80% global Y ningún TIPO de acción <60% (anti-regresión por
dominio, CLAUDE.md). Verifica por título de ventana / display / contenido UIA.
NO envía mensajes a terceros (open_chat solo abre; el type en chat va a un borrador
que NO se envía en este harness — los casos de chat acá son open_chat sin send).
"""
import os, sys, time, json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")
import win32gui, win32con

def _sub(code):
    return subprocess.run(["python", "-c", code], capture_output=True, text=True, timeout=20).stdout.strip()

def fg_title():
    return win32gui.GetWindowText(win32gui.GetForegroundWindow()) or ""

def win_title(substr):
    o = [""]
    def c(h, _):
        t = win32gui.GetWindowText(h)
        if substr.lower() in t.lower() and not t.lower().startswith("discord overlay"):
            o[0] = t
        return True
    win32gui.EnumWindows(c, None)
    return o[0]

def calc_display():
    return _sub('import uiautomation as a\n'
        'for w in a.GetRootControl().GetChildren():\n'
        ' if "alculadora" in (w.Name or ""):\n'
        '  r=w.TextControl(AutomationId="CalculatorResults",searchDepth=10)\n'
        '  print(r.Name if r.Exists(0.5) else "NONE");break\n'
        'else: print("NOCALC")')

def npad_has(word, key="notas"):
    # UNA sola ventana de notepad abierta (cerramos las demás): matchear por "notas"
    # /"notepad" alcanza, y el título cambia al texto tecleado (perdería "gemma4_cu").
    code=('import uiautomation as a\nf=False\n'
        'for w in a.GetRootControl().GetChildren():\n'
        ' nm=(w.Name or "").lower()\n'
        ' if "notas" in nm or "notepad" in nm:\n'
        '  s=list(w.GetChildren());d=0\n'
        '  while s and d<600:\n'
        '   el=s.pop();d+=1\n'
        '   try:\n    v=el.GetValuePattern().Value or ""\n   except Exception:\n    v=el.Name or ""\n'
        '   if "'+word.lower()+'" in (v or "").lower(): f=True;break\n'
        '   try: s.extend(el.GetChildren())\n   except Exception: pass\n'
        'print("YES" if f else "NO")')
    return _sub(code) == "YES"

def ensure_open(exe, substr):
    if not win_title(substr):
        subprocess.Popen(exe, shell=True); time.sleep(2.5)

def restore(substr):
    hd=[]
    def c(h,_):
        t=win32gui.GetWindowText(h)
        if substr.lower() in t.lower() and win32gui.IsWindowVisible(h) and not t.lower().startswith("discord overlay"): hd.append(h)
        return True
    win32gui.EnumWindows(c,None)
    if hd: win32gui.ShowWindow(hd[0], win32con.SW_RESTORE)

def build():
    from gemma4_agent.agent import Gemma4Agent
    from gemma4_agent.config import AgentConfig
    return Gemma4Agent(AgentConfig.from_env())

# ---- misiones: (tipo, comando, setup_fn|None, verify_fn) ----
def v_calc(expect):
    def f():
        d=calc_display() or ""; dig="".join(c for c in d if c.isdigit())
        return expect in dig or dig.endswith(expect)
    return f
def v_titlehas(substr, word):
    # verificar contra la ventana en FOREGROUND (la que el executor acaba de
    # operar): con varias ventanas del mismo app, win_title() devuelve una
    # arbitraria. El foreground es la afectada. Fallback a win_title si el fg no
    # matchea el app (por si otra ventana robó foco).
    def f():
        fg = fg_title().lower()
        if substr.lower() in fg:
            return word.lower() in fg
        return word.lower() in (win_title(substr) or "").lower()
    return f
def v_npad(word):
    # con UNA sola ventana de notepad (cerramos las demás antes), leer su contenido
    # por UIA es fiable; verifica que la PALABRA tecleada quedó en el documento.
    return lambda: npad_has(word)

def setup_calc_clear():
    from gemma4_agent import gui_safety
    gui_safety.reset_action_budget()
    # focus calc + Escape para limpiar
    try:
        AG.tools._focus_window_chen("Calculadora"); time.sleep(0.3)
        AG.tools.execute("gui", {"action":"keypress","keys":"escape"}); time.sleep(0.2)
    except Exception: pass
def setup_opera_home():
    pass
def setup_discord_ron():
    from gemma4_agent import gui_safety
    gui_safety.reset_action_budget()
    try:
        AG.tools._focus_window_chen("Discord"); time.sleep(0.8)
        AG.tools.execute("gui",{"action":"keypress","keys":"ctrl+k"}); time.sleep(0.6)
        AG.tools.execute("gui",{"action":"type","text":"Ron92"}); time.sleep(0.8)
        AG.tools.execute("gui",{"action":"keypress","keys":"enter"}); time.sleep(1.0)
    except Exception: pass

MISSIONS = [
    # --- calc: type + keypress (operar app abierta) ---
    ("calc", "calculá 2+2 en la calculadora", setup_calc_clear, v_calc("4")),
    ("calc", "en la calculadora escribí 7*6 y apretá igual", setup_calc_clear, v_calc("42")),
    ("calc", "hacé 9*9 en la calculadora", setup_calc_clear, v_calc("81")),
    ("calc", "calculá 100-58 en la calculadora", setup_calc_clear, v_calc("42")),
    # --- browser: open_url (navegar) ---
    ("browser", "andá a opera y entrá a python.org", None, v_titlehas("Opera","python")),
    ("browser", "en opera entrá a github.com", None, v_titlehas("Opera","github")),
    ("browser", "abrí wikipedia.org en opera", None, v_titlehas("Opera","wiki")),
    ("browser", "en opera andá a example.com", None, v_titlehas("Opera","example")),
    # --- discord: open_chat (navegar a un chat, SIN enviar) ---
    ("chat", "andá a discord al chat de cbayeah", setup_discord_ron, v_titlehas("Discord","cbayeah")),
    ("chat", "entrá a discord al chat de juanpi", setup_discord_ron, v_titlehas("Discord","juanpi")),
    ("chat", "en discord abrí el chat de pierosky", setup_discord_ron, v_titlehas("Discord","pierosky")),
    ("chat", "andá a discord a ShooterCOCK", setup_discord_ron, v_titlehas("Discord","shooter")),
    # --- notepad: type (escribir en doc propio) ---
    # (se prepara una sola ventana propia; cada caso escribe una palabra única)
]

print("=== OPCIÓN A (ejecutor de planes) — apps variadas ===", flush=True)
AG = build()
AG.run_text("hola")
from gemma4_agent.computer_use import plan_for, PlanExecutor
EXEC = PlanExecutor(AG)

# asegurar apps abiertas
ensure_open("calc.exe", "alculadora")
ensure_open(r'"C:\Users\usuario\AppData\Local\Programs\Opera GX\opera.exe"', "Opera")
restore("Discord"); restore("Opera"); restore("alculadora")
time.sleep(1.0)

# --- notepad: UNA sola ventana limpia (el Win11 Notepad es de instancia única con
# pestañas; acumular ventanas hace que focus() caiga en una vieja y el type/verify
# midan mal — NO es bug del executor, es el fixture). Cerramos notepad UNA vez
# (ram.txt NO está abierto ahora — verificado) y abrimos UNA ventana de test.
import tempfile
subprocess.run(["taskkill","/F","/IM","notepad.exe"], capture_output=True)
subprocess.run(["taskkill","/F","/IM","Notepad.exe"], capture_output=True)
time.sleep(1.0)
_nf = Path(tempfile.mkdtemp())/"gemma4_cu.txt"; _nf.write_text("", encoding="utf-8")
subprocess.Popen(["notepad.exe", str(_nf)]); time.sleep(2.2)
NPAD_CASES = [
    ("notepad", "escribí murcielago en el bloc de notas", "murcielago"),
    ("notepad", "en el bloc de notas escribí paralelogramo", "paralelogramo"),
    ("notepad", "escribí helicoptero en el bloc de notas", "helicoptero"),
    ("notepad", "en el bloc de notas escribí computadora", "computadora"),
]

results = []
def run_mission(kind, cmd, setup, verify):
    if setup: setup()
    plan = plan_for(AG, cmd)
    if not plan:
        results.append({"kind":kind,"cmd":cmd,"ok":False,"plan":None,"reason":"no_plan"})
        print(f"  FAIL [{kind}] no-plan | {cmd!r}", flush=True); return
    res = EXEC.execute(plan, "cu")
    time.sleep(0.8)
    ok = False
    try: ok = verify()
    except Exception: ok = False
    ops = [s["op"] for s in plan]
    results.append({"kind":kind,"cmd":cmd,"ok":ok,"plan_ops":ops,"exec_ok":res.get("ok")})
    print(f"  {'OK ' if ok else 'FAIL'} [{kind}] ops={ops} exec={res.get('ok')} | {cmd[:42]!r}", flush=True)

for kind, cmd, setup, verify in MISSIONS:
    run_mission(kind, cmd, setup, verify)
# notepad: limpiar el campo de LA MISMA ventana que el executor va a enfocar
# ("Bloc de notas"), no una específica — así el clear y el type caen en la misma.
for kind, cmd, word in NPAD_CASES:
    from gemma4_agent import gui_safety
    gui_safety.reset_action_budget()
    try:
        AG.tools._focus_window_chen("Bloc de notas"); time.sleep(0.3)
        AG.tools.execute("gui",{"action":"keypress","keys":"ctrl+a"}); time.sleep(0.1)
        AG.tools.execute("gui",{"action":"keypress","keys":"delete"}); time.sleep(0.1)
    except Exception: pass
    run_mission(kind, cmd, None, v_npad(word))

# --- reporte con gate por tipo ---
out = ROOT/"scripts"/"gui_eval"/"_measure_cu_optionA_results.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
from collections import defaultdict
by = defaultdict(lambda:[0,0])
for r in results:
    by[r["kind"]][1]+=1
    if r["ok"]: by[r["kind"]][0]+=1
tot_ok=sum(1 for r in results if r["ok"]); tot=len(results)
print(f"\n>> OPCIÓN A global: {tot_ok}/{tot} = {100*tot_ok//max(tot,1)}%", flush=True)
worst=1.0
for k,(o,n) in sorted(by.items()):
    pct=o/max(n,1); worst=min(worst,pct)
    print(f"   {k}: {o}/{n} = {int(100*pct)}%", flush=True)
gate = (tot_ok/max(tot,1) >= 0.80) and (worst >= 0.60)
print(f">> GATE (global>=80% Y peor-tipo>=60%): {'PASA' if gate else 'NO PASA'}", flush=True)
print("WROTE", out, flush=True)
