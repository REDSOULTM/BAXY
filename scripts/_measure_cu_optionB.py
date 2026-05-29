"""Mide la OPCIÓN B (clasificador verbo->primitiva por embeddings) en las MISMAS
misiones que la Opción A, para comparar. B clasifica el objetivo a UNA primitiva por
embeddings y la ejecuta (antepone focus_app si hay app abierta). Limitación esperada:
NO compone multi-paso (calc type+keypress, chat open+type+send) — lo medimos honesto.

Mismo gate que A (global>=80% Y peor-tipo>=60%). Verifica por estado del SO.
"""
import os, sys, time, json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")
import win32gui, win32con

def _sub(code):
    return subprocess.run(["python","-c",code], capture_output=True, text=True, timeout=20).stdout.strip()
def win_title(s):
    o=[""]
    def c(h,_):
        t=win32gui.GetWindowText(h)
        if s.lower() in t.lower() and not t.lower().startswith("discord overlay"): o[0]=t
        return True
    win32gui.EnumWindows(c,None); return o[0]
def calc_display():
    return _sub('import uiautomation as a\n'
        'for w in a.GetRootControl().GetChildren():\n if "alculadora" in (w.Name or ""):\n'
        '  r=w.TextControl(AutomationId="CalculatorResults",searchDepth=10)\n'
        '  print(r.Name if r.Exists(0.5) else "NONE");break\nelse: print("NOCALC")')
def npad_has(word, key="gemma4_cu"):
    code=('import uiautomation as a\nf=False\n'
        'for w in a.GetRootControl().GetChildren():\n if "'+key+'" in (w.Name or "").lower():\n'
        '  s=list(w.GetChildren());d=0\n  while s and d<600:\n   el=s.pop();d+=1\n'
        '   try:\n    v=el.GetValuePattern().Value or ""\n   except Exception:\n    v=el.Name or ""\n'
        '   if "'+word.lower()+'" in (v or "").lower(): f=True;break\n'
        '   try: s.extend(el.GetChildren())\n   except Exception: pass\nprint("YES" if f else "NO")')
    return _sub(code)=="YES"
def ensure_open(exe, s):
    if not win_title(s): subprocess.Popen(exe, shell=True); time.sleep(2.5)
def restore(s):
    hd=[]
    def c(h,_):
        t=win32gui.GetWindowText(h)
        if s.lower() in t.lower() and win32gui.IsWindowVisible(h) and not t.lower().startswith("discord overlay"): hd.append(h)
        return True
    win32gui.EnumWindows(c,None)
    if hd: win32gui.ShowWindow(hd[0], win32con.SW_RESTORE)
def build():
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig
    return Gemma4Agent(AgentConfig.from_env())

def v_calc(e):
    def f():
        d=calc_display() or ""; dig="".join(c for c in d if c.isdigit()); return e in dig or dig.endswith(e)
    return f
def v_th(s,w): return lambda: w.lower() in (win_title(s) or "").lower()
def v_np(w): return lambda: npad_has(w)

print("=== OPCIÓN B (embeddings verbo->primitiva) — apps variadas ===", flush=True)
AG=build(); AG.run_text("hola")
from gemma4_agent.computer_use_pkg.computer_use_b import run_single_primitive
from gemma4_agent.computer_use_pkg import gui_safety


def setup_calc():
    gui_safety.reset_action_budget()
    try: AG.tools._focus_window_chen("Calculadora"); time.sleep(0.3); AG.tools.execute("gui",{"action":"keypress","keys":"escape"}); time.sleep(0.2)
    except Exception: pass
def setup_disc():
    gui_safety.reset_action_budget()
    try:
        AG.tools._focus_window_chen("Discord"); time.sleep(0.8)
        AG.tools.execute("gui",{"action":"keypress","keys":"ctrl+k"}); time.sleep(0.6)
        AG.tools.execute("gui",{"action":"type","text":"Ron92"}); time.sleep(0.8)
        AG.tools.execute("gui",{"action":"keypress","keys":"enter"}); time.sleep(1.0)
    except Exception: pass

MISSIONS = [
    ("calc","calculá 2+2 en la calculadora",setup_calc,v_calc("4")),
    ("calc","en la calculadora escribí 7*6 y apretá igual",setup_calc,v_calc("42")),
    ("calc","hacé 9*9 en la calculadora",setup_calc,v_calc("81")),
    ("calc","calculá 100-58 en la calculadora",setup_calc,v_calc("42")),
    ("browser","andá a opera y entrá a python.org",None,v_th("Opera","python")),
    ("browser","en opera entrá a github.com",None,v_th("Opera","github")),
    ("browser","abrí wikipedia.org en opera",None,v_th("Opera","wiki")),
    ("browser","en opera andá a example.com",None,v_th("Opera","example")),
    ("chat","andá a discord al chat de cbayeah",setup_disc,v_th("Discord","cbayeah")),
    ("chat","entrá a discord al chat de juanpi",setup_disc,v_th("Discord","juanpi")),
    ("chat","en discord abrí el chat de pierosky",setup_disc,v_th("Discord","pierosky")),
    ("chat","andá a discord a ShooterCOCK",setup_disc,v_th("Discord","shooter")),
]
ensure_open("calc.exe","alculadora")
ensure_open(r'"C:\Users\usuario\AppData\Local\Programs\Opera GX\opera.exe"',"Opera")
restore("Discord"); restore("Opera"); restore("alculadora"); time.sleep(1.0)
import tempfile
_nf=Path(tempfile.mkdtemp())/"gemma4_cu.txt"; _nf.write_text("",encoding="utf-8")
subprocess.Popen(["notepad.exe",str(_nf)]); time.sleep(2.0)
NPAD=[("notepad","escribí hola mundo en el bloc de notas","hola mundo"),
      ("notepad","en el bloc de notas escribí prueba uno","prueba uno"),
      ("notepad","escribí informe final en el bloc de notas","informe final"),
      ("notepad","en el bloc de notas escribí nota importante","nota importante")]

results=[]
def run(kind,cmd,setup,verify):
    if setup: setup()
    res=run_single_primitive(AG, cmd)
    if res is None:
        results.append({"kind":kind,"cmd":cmd,"ok":False,"reason":"no_classify"})
        print(f"  FAIL [{kind}] no-classify | {cmd[:42]!r}", flush=True); return
    time.sleep(0.8)
    ok=False
    try: ok=verify()
    except Exception: ok=False
    results.append({"kind":kind,"cmd":cmd,"ok":ok,"primitive":res.get("primitive"),"exec_ok":res.get("ok")})
    print(f"  {'OK ' if ok else 'FAIL'} [{kind}] prim={res.get('primitive')} | {cmd[:42]!r}", flush=True)

for kind,cmd,setup,verify in MISSIONS: run(kind,cmd,setup,verify)
for kind,cmd,word in NPAD:
    gui_safety.reset_action_budget()
    try:
        AG.tools._focus_window_chen("gemma4_cu"); time.sleep(0.3)
        AG.tools.execute("gui",{"action":"keypress","keys":"ctrl+a"}); time.sleep(0.1)
        AG.tools.execute("gui",{"action":"keypress","keys":"delete"}); time.sleep(0.1)
    except Exception: pass
    run(kind,cmd,None,v_np(word))

out=ROOT/"scripts"/"gui_eval"/"_measure_cu_optionB_results.json"
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
from collections import defaultdict
by=defaultdict(lambda:[0,0])
for r in results:
    by[r["kind"]][1]+=1
    if r["ok"]: by[r["kind"]][0]+=1
tot_ok=sum(1 for r in results if r["ok"]); tot=len(results)
print(f"\n>> OPCIÓN B global: {tot_ok}/{tot} = {100*tot_ok//max(tot,1)}%", flush=True)
worst=1.0
for k,(o,n) in sorted(by.items()):
    p=o/max(n,1); worst=min(worst,p); print(f"   {k}: {o}/{n} = {int(100*p)}%", flush=True)
print(f">> GATE (global>=80% Y peor-tipo>=60%): {'PASA' if (tot_ok/max(tot,1)>=0.8 and worst>=0.6) else 'NO PASA'}", flush=True)
print("WROTE", out, flush=True)
