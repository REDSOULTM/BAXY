"""Validación FINAL: la capa universal a través del AGENTE REAL (run_text), el camino
de producción (no plan_for directo). Apps variadas, verificado por estado del SO.
Confirma que _try_computer_use fira en run_content end-to-end."""
import os, sys, time, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")
import win32gui, win32con

def _sub(c): return subprocess.run(["python","-c",c],capture_output=True,text=True,timeout=20).stdout.strip()
def calc_disp():
    return _sub('import uiautomation as a\nfor w in a.GetRootControl().GetChildren():\n if "alculadora" in (w.Name or ""):\n  r=w.TextControl(AutomationId="CalculatorResults",searchDepth=10)\n  print(r.Name if r.Exists(0.5) else "NONE");break')
def fgt(): return win32gui.GetWindowText(win32gui.GetForegroundWindow()) or ""
def restore(s):
    hd=[]
    def c(h,_):
        t=win32gui.GetWindowText(h)
        if s.lower() in t.lower() and win32gui.IsWindowVisible(h) and not t.lower().startswith("discord overlay"): hd.append(h)
        return True
    win32gui.EnumWindows(c,None)
    if hd: win32gui.ShowWindow(hd[0], win32con.SW_RESTORE)

# apps estables
subprocess.run(["taskkill","/F","/IM","CalculatorApp.exe"],capture_output=True); time.sleep(0.5)
subprocess.Popen(["calc.exe"]); time.sleep(2.5)
restore("Opera"); restore("Discord"); time.sleep(1.0)

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra.config import AgentConfig
ag=Gemma4Agent(AgentConfig.from_env()); ag.run_text("hola")

def fired(ag, cmd):
    seen=[]
    orig=ag.trace.event
    def spy(t,n,**k): seen.append(n); return orig(t,n,**k)
    ag.trace.event=spy
    r=ag.run_text(cmd)
    ag.trace.event=orig
    return r, ("computer_use_plan" in seen)

CASES=[
    ("calc","calcula 8 por 4 en la calculadora", lambda: "32" in (calc_disp() or "")),
    ("calc","en la calculadora hace 15+15", lambda: "30" in (calc_disp() or "")),
    ("calc","calcula 50-8 en la calculadora", lambda: "42" in (calc_disp() or "")),
    ("browser","en opera entra a python.org", lambda: "python" in fgt().lower()),
    ("browser","anda a opera y entra a github.com", lambda: "github" in fgt().lower()),
    ("chat","anda a discord al chat de cbayeah", lambda: "cbayeah" in (_disc() or "").lower()),
    ("chat","entra a discord al chat de juanpi", lambda: "juanpi" in (_disc() or "").lower()),
]
def _disc():
    o=[""]
    def c(h,_):
        t=win32gui.GetWindowText(h)
        if "Discord" in t and not t.startswith("Discord Overlay"): o[0]=t
        return True
    win32gui.EnumWindows(c,None); return o[0]

ok=0; fires=0
for kind,cmd,verify in CASES:
    if kind=="calc":
        from gemma4_agent import gui_safety; gui_safety.reset_action_budget()
        try: ag.tools._focus_window_chen("Calculadora"); time.sleep(0.3); ag.tools.execute("gui",{"action":"keypress","keys":"escape"}); time.sleep(0.2)
        except Exception: pass
    r,fr=fired(ag,cmd); time.sleep(0.8)
    v=False
    try: v=verify()
    except Exception: v=False
    ok+=v; fires+=fr
    print(f"  {'OK ' if v else 'FAIL'} fired_cu={fr} [{kind}] {cmd[:36]!r} -> {(r.content or '').encode('ascii','replace').decode()[:42]!r}", flush=True)

print(f"\n>> WIRED e2e (run_text real): {ok}/{len(CASES)} ok, {fires}/{len(CASES)} dispararon computer_use", flush=True)
