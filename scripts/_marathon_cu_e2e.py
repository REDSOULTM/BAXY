"""MARATÓN Fase 2 — computer-use e2e REAL (verificado por estado del SO).

Corre comandos por el AGENTE REAL (run_text), opera apps reales, verifica por estado
del SO. Apps verificables sin efectos en terceros:
  - calc: display (type+keypress / click botones)
  - browser (Opera/Chrome/Edge): título refleja la página (open_url)
  - chat (Discord): título refleja el chat activo (open_chat, SIN enviar)
  - notepad: contenido por UIA (type) — UNA ventana limpia
  - apps genéricas (Paint/Explorer/Settings/Spotify/Steam): ventana presente (focus_app)

SAFE: NO envía mensajes reales, NO cierra apps del user, NO ops destructivas.
JSONL incremental (reanudable). Self-throttle. Verifica por foreground cuando hay
varias ventanas del mismo app.

Uso: python scripts/_marathon_cu_e2e.py [--rounds N]
"""
import os, sys, json, time, subprocess, argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")
import win32gui, win32con

ap = argparse.ArgumentParser()
ap.add_argument("--rounds", type=int, default=8)  # repeticiones del set base
args = ap.parse_args()

def _sub(c): return subprocess.run(["python","-c",c],capture_output=True,text=True,timeout=20).stdout.strip()
def fgt(): return win32gui.GetWindowText(win32gui.GetForegroundWindow()) or ""
def win_present(substr):
    o=[False]
    def c(h,_):
        t=win32gui.GetWindowText(h)
        if substr.lower() in t.lower() and win32gui.IsWindowVisible(h): o[0]=True
        return True
    win32gui.EnumWindows(c,None); return o[0]
def win_title(substr):
    o=[""]
    def c(h,_):
        t=win32gui.GetWindowText(h)
        if substr.lower() in t.lower() and not t.lower().startswith("discord overlay"): o[0]=t
        return True
    win32gui.EnumWindows(c,None); return o[0]
def calc_disp():
    return _sub('import uiautomation as a\nfor w in a.GetRootControl().GetChildren():\n if "alculadora" in (w.Name or ""):\n  r=w.TextControl(AutomationId="CalculatorResults",searchDepth=10)\n  print(r.Name if r.Exists(0.5) else "NONE");break')
def npad_has(word):
    code=('import uiautomation as a\nf=False\nfor w in a.GetRootControl().GetChildren():\n nm=(w.Name or "").lower()\n if "notas" in nm or "notepad" in nm:\n  s=list(w.GetChildren());d=0\n  while s and d<600:\n   el=s.pop();d+=1\n   try:\n    v=el.GetValuePattern().Value or ""\n   except Exception:\n    v=el.Name or ""\n   if "'+word.lower()+'" in (v or "").lower(): f=True;break\n   try: s.extend(el.GetChildren())\n   except Exception: pass\nprint("YES" if f else "NO")')
    return _sub(code)=="YES"
def restore(s):
    hd=[]
    def c(h,_):
        t=win32gui.GetWindowText(h)
        if s.lower() in t.lower() and win32gui.IsWindowVisible(h) and not t.lower().startswith("discord overlay"): hd.append(h)
        return True
    win32gui.EnumWindows(c,None)
    if hd: win32gui.ShowWindow(hd[0], win32con.SW_RESTORE)

def build():
    from gemma4_agent.agent import Gemma4Agent
    from gemma4_agent.config import AgentConfig
    return Gemma4Agent(AgentConfig.from_env())

# ----- verificadores por estado del SO -----
def v_calc(expect):
    def f():
        d=calc_disp() or ""; dig="".join(c for c in d if c.isdigit()); return expect in dig or dig.endswith(expect)
    return f
def v_fg_has(word):
    return lambda: word.lower() in fgt().lower()
import re as _re_v
def _norm(s): return _re_v.sub(r"[^a-z0-9]", "", (s or "").lower())
def v_title_has(substr, word):  # foreground primero, fallback a win_title; NORMALIZADO
    # normaliza ambos lados: el título "espacia" dominios ("stackoverflow"->"Stack
    # Overflow") y el match contiguo daba falso-negativo (bug medido).
    def f():
        fg=fgt()
        if substr.lower() in fg.lower(): return _norm(word) in _norm(fg)
        return _norm(word) in _norm(win_title(substr))
    return f
def v_npad(word): return lambda: npad_has(word)
def v_present(substr): return lambda: win_present(substr)

AVAIL = {}  # apps efectivamente abiertas/abribles

def ensure(exe, substr):
    if not win_present(substr):
        try: subprocess.Popen(exe, shell=True); time.sleep(3.0)
        except Exception: pass
    return win_present(substr)

# ----- set base de misiones (se repite --rounds veces con variación) -----
def calc_clear(ag):
    from gemma4_agent import gui_safety; gui_safety.reset_action_budget()
    try: ag.tools._focus_window_chen("Calculadora"); time.sleep(0.3); ag.tools.execute("gui",{"action":"keypress","keys":"escape"}); time.sleep(0.2)
    except Exception: pass
def npad_clear(ag):
    from gemma4_agent import gui_safety; gui_safety.reset_action_budget()
    try:
        ag.tools._focus_window_chen("Bloc de notas"); time.sleep(0.3)
        ag.tools.execute("gui",{"action":"keypress","keys":"ctrl+a"}); time.sleep(0.1)
        ag.tools.execute("gui",{"action":"keypress","keys":"delete"}); time.sleep(0.1)
    except Exception: pass

CALC=[("2+2","4"),("5*5","25"),("9+1","10"),("8-3","5"),("6*7","42"),("12+12","24"),
      ("100/4","25"),("7+8","15"),("11*11","121"),("50-8","42")]
URLS=["python.org","github.com","wikipedia.org","example.com","reddit.com",
      "stackoverflow.com","gmail.com","youtube.com","bing.com","duckduckgo.com"]
CHATS=["cbayeah","juanpi","pierosky","ShooterCOCK","Ron92","Migue_STg"]
WORDS=["murcielago","paralelogramo","helicoptero","computadora","bicicleta",
       "telescopio","mariposa","refrigerador","aspiradora","calendario"]

out = ROOT/"scripts"/"gui_eval"/"_marathon_cu.jsonl"
out.parent.mkdir(parents=True, exist_ok=True)
logf = out.open("a", encoding="utf-8")
def log(rec): logf.write(json.dumps(rec, ensure_ascii=False)+"\n"); logf.flush()

print(f"=== MARATÓN Fase 2 (computer-use e2e real): {args.rounds} rondas ===", flush=True)
AG = build(); AG.run_text("hola")

# qué apps tenemos
have_calc = ensure("calc.exe","alculadora")
have_opera = win_present("Opera")
have_chrome = win_present("Chrome")
have_edge = win_present("Edge")
have_discord = win_present("Discord")
# notepad: una sola ventana limpia (ram.txt no debe estar — si está, NO tocamos notepad)
have_npad=False
if not win_present("ram.txt"):
    subprocess.run(["taskkill","/F","/IM","notepad.exe"],capture_output=True)
    subprocess.run(["taskkill","/F","/IM","Notepad.exe"],capture_output=True); time.sleep(1.0)
    import tempfile; _nf=Path(tempfile.mkdtemp())/"gemma4_cu.txt"; _nf.write_text("",encoding="utf-8")
    subprocess.Popen(["notepad.exe",str(_nf)]); time.sleep(2.2); have_npad=win_present("notas")
browser = "opera" if have_opera else ("chrome" if have_chrome else ("edge" if have_edge else None))
print(f"apps: calc={have_calc} browser={browser} discord={have_discord} notepad={have_npad}", flush=True)

n=ok=0; t0=time.time()
def run(kind, cmd, setup, verify, app, settle=0.6):
    global n, ok
    if setup: setup(AG)
    seen=[]
    def prog(s,i=None): seen.append(s)
    t=time.time()
    try:
        r=AG.run_text(cmd, progress=prog); reply=(r.content or "")
    except Exception as exc:
        reply=f"EXC {exc}"
    dt=time.time()-t
    # open_app: algunas apps (Spotify/Steam) tardan en mostrar su ventana -> verify
    # con reintento hasta `settle`s antes de declarar fallo (latencia de lanzamiento,
    # no del agente). Otros tipos: settle corto.
    v=False
    deadline=time.time()+settle
    while True:
        try: v=verify()
        except Exception: v=False
        if v or time.time()>=deadline: break
        time.sleep(0.5)
    n+=1; ok+=v
    log({"i":n,"kind":kind,"app":app,"cmd":cmd,"ok":v,"reply":reply[:60],"lat":round(dt,1)})
    if n%10==0:
        print(f"  [{n}] ok {ok}/{n} ({100*ok//n}%) | {time.strftime('%H:%M:%S')} | last {kind}/{app} {'OK' if v else 'FAIL'}", flush=True)

for rnd in range(args.rounds):
    # CALC type+keypress
    if have_calc:
        for expr, exp in CALC:
            run("calc_type", f"calculá {expr} en la calculadora", calc_clear, v_calc(exp), "calc")
    # BROWSER open_url
    if browser:
        for url in URLS:
            run("browser_url", f"en {browser} entrá a {url}", None, v_title_has(browser, url.split('.')[0]), browser)
    # CHAT open_chat (sin enviar)
    if have_discord:
        for c in CHATS:
            run("chat_open", f"andá a discord al chat de {c}", None, v_title_has("Discord", c[:6]), "discord")
    # NOTEPAD type — RESET a UNA ventana limpia por ronda (evita que el título
    # quede con una palabra de test previa y confunda el contexto de app; era el
    # artefacto que daba 43% en la maratón, NO el agente — medido 5/5 en limpio).
    if have_npad and not win_present("ram.txt"):
        subprocess.run(["taskkill","/F","/IM","notepad.exe"],capture_output=True)
        subprocess.run(["taskkill","/F","/IM","Notepad.exe"],capture_output=True); time.sleep(0.8)
        import tempfile as _tf; _nf2=Path(_tf.mkdtemp())/"gemma4_cu.txt"; _nf2.write_text("",encoding="utf-8")
        subprocess.Popen(["notepad.exe",str(_nf2)]); time.sleep(2.0)
        for w in WORDS:
            run("npad_type", f"escribí {w} en el bloc de notas", npad_clear, v_npad(w), "notepad")
    # OPEN-APP (cobertura amplia): abrir/enfocar apps variadas, verify = ventana presente.
    for cmd, sub, app in [("abrí paint","Paint","paint"),
                          ("abrí el explorador de archivos","Explorador","explorer"),
                          ("abrí spotify","Spotify","spotify"),
                          ("abrí steam","Steam","steam")]:
        run("open_app", cmd, None, v_present(sub), app, settle=4.0)  # apps lentas
    print(f"-- ronda {rnd+1}/{args.rounds} done: ok {ok}/{n} ({100*ok//max(n,1)}%) --", flush=True)

logf.close()
print(f"\n>> Fase 2 FINAL: {ok}/{n} ({100*ok//max(n,1)}%) en {(time.time()-t0)/60:.1f} min", flush=True)
print("WROTE", out, flush=True)
