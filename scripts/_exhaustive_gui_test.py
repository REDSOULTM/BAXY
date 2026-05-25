"""Harness exhaustivo computer-use (autonomo). Mide por ESTADO DEL SO.

DOS artefactos de test que NO son bugs del agente (documentados 2026-05-25):
 1. COMError de uiautomation en loops largos -> leemos el display en SUBPROCESO
    fresco (COM limpio cada vez).
 2. action-budget por turno (gui_safety, tope 6 acciones físicas) -> en prod se
    RESETEA por turno de voz (agent.py:679). Acá lo reseteamos por CASO para
    simular que cada caso es un turno nuevo del usuario. Sin esto, el harness
    chocaba el cap al 3er caso ("anda 2-3 y muere") — era contaminación del test,
    no del agente.
"""
import sys, time, json, subprocess, tempfile, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gemma4_agent.tools import ToolRegistry
from gemma4_agent.memory import MemoryStore
from gemma4_agent import gui_safety

tmp = Path(tempfile.mkdtemp())
reg = ToolRegistry(memory=MemoryStore(tmp/"m.json"), captures_dir=tmp)
results = {}

def new_turn(goal=""):
    """Simula el inicio de un turno de voz: presupuesto de acciones fresco."""
    gui_safety.reset_action_budget()
    gui_safety.set_turn_goal(goal)

def _read_subproc(code):
    """Lee estado UIA en un subproceso Python fresco (COM limpio, evita COMError)."""
    r = subprocess.run(["python","-c",code], capture_output=True, text=True, timeout=20)
    return r.stdout.strip()

def calc_display():
    code=('import uiautomation as a\n'
          'for w in a.GetRootControl().GetChildren():\n'
          ' if "alculadora" in (w.Name or ""):\n'
          '  r=w.TextControl(AutomationId="CalculatorResults",searchDepth=10)\n'
          '  print(r.Name if r.Exists(0.5) else "NONE");break')
    return _read_subproc(code)

def npad_has(text):
    safe=text.replace('"','')
    key=(_NPAD_TITLEKEY or "gemma4_npad_test")
    code=('import uiautomation as a\n'
          'found=False\n'
          'for w in a.GetRootControl().GetChildren():\n'
          ' nm=(w.Name or "").lower()\n'
          ' if "'+key+'" in nm:\n'  # SOLO nuestro archivo de test, no el del user
          '  s=list(w.GetChildren());d=0\n'
          '  while s and d<500:\n'
          '   el=s.pop();d+=1\n'
          '   try:\n'
          '    vp=el.GetValuePattern();v=vp.Value or ""\n'
          '   except Exception:\n'
          '    v=el.Name or ""\n'
          '   if "'+safe.lower()+'" in (v or "").lower(): found=True;break\n'
          '   try: s.extend(el.GetChildren())\n'
          '   except Exception: pass\n'
          'print("YES" if found else "NO")')
    return _read_subproc(code)=="YES"

def ensure_calc():
    """Lanza calc UNA vez si no está; reutiliza la instancia (como en uso real)."""
    n=_read_subproc('import uiautomation as a;print(sum(1 for w in a.GetRootControl().GetChildren() if "alculadora" in (w.Name or "")))')
    if n=="0" or not n:
        subprocess.Popen(["calc.exe"]); time.sleep(2.5)

_NPAD_FILE = None   # ruta del fixture EXCLUSIVO de este test (nunca el del user)
_NPAD_TITLEKEY = None

def ensure_notepad():
    """Abre un archivo TXT EXCLUSIVO del test (gemma4_npad_test_*.txt) para NO
    tocar jamás un Notepad del usuario. El Notepad moderno de Win11 es de UNA
    instancia con pestañas: Popen('notepad') reusa la ventana del usuario (bug
    medido 2026-05-25 — escribió en ram.txt del user). Guarda: solo escribimos si
    el título en foco contiene NUESTRO nombre de archivo único; si no, abortamos."""
    global _NPAD_FILE, _NPAD_TITLEKEY
    _NPAD_FILE = tmp/"gemma4_npad_test.txt"
    _NPAD_FILE.write_text("", encoding="utf-8")
    _NPAD_TITLEKEY = "gemma4_npad_test"
    subprocess.Popen(["notepad.exe", str(_NPAD_FILE)]); time.sleep(2.2)

def npad_is_ours():
    """True solo si el foreground es NUESTRO archivo de test (no el del user)."""
    import win32gui
    t = win32gui.GetWindowText(win32gui.GetForegroundWindow()) or ""
    return _NPAD_TITLEKEY in t.lower()

# AREA 1: CALC type_into + enter (10) — instancia reutilizada, Escape entre casos.
calc_cases=[("2+2","4"),("5+3","8"),("7*6","42"),("100-58","42"),("9*9","81"),
            ("12+8","20"),("50-5","45"),("8*8","64"),("11+11","22"),("144-44","100")]
ensure_calc()
results["calc"]=[]; print("=== CALC x10 (type_into+enter) ===",flush=True)
for expr,exp in calc_cases:
    new_turn(f"calculá {expr}")
    reg.execute("gui",{"action":"keypress","keys":"escape"});time.sleep(0.12)
    reg.execute("gui",{"action":"type_into","text":expr,"window":"Calculadora"});time.sleep(0.2)
    reg.execute("gui",{"action":"keypress","keys":"enter"});time.sleep(0.45)
    d=calc_display() or "";dig="".join(c for c in d if c.isdigit());ok=exp in dig
    results["calc"].append({"expr":expr,"exp":exp,"display":d,"ok":ok})
    print(f"  {expr}={exp}: {d!r} {'OK' if ok else 'FAIL'}",flush=True)

# AREA 2: NOTEPAD type_into (10) — instancia reutilizada, Ctrl+A + Delete entre casos.
npad_cases=["hola mundo","informe final","accion rapida","prueba uno dos","comprar leche",
            "reunion a las cinco","proyecto alpha","nota importante","lista de tareas","mensaje test"]
results["notepad"]=[]; print("=== NOTEPAD x10 (type_into append, archivo propio ÚNICO) ===",flush=True)
# Notepad Win11 es de UNA instancia con pestañas y dispara diálogos de Guardar al
# limpiar/reabrir/multi-abrir -> mal fixture si se reusa o se multiplica. UNA sola
# ventana de archivo propio, APPEND (Ctrl+End + type + Enter) sin limpiar ni
# guardar. Verificamos que CADA línea quede en el buffer por su nombre único.
import win32gui
_NK = "gemma4_npad_one"
_nf = tmp/f"{_NK}.txt"; _nf.write_text("", encoding="utf-8")
subprocess.Popen(["notepad.exe", str(_nf)]); time.sleep(2.2)
for txt in npad_cases:
    new_turn(f"escribí {txt}")
    reg._focus_window_chen(_NK); time.sleep(0.35)
    fg=(win32gui.GetWindowText(win32gui.GetForegroundWindow()) or "").lower()
    if _NK not in fg:
        results["notepad"].append({"text":txt,"ok":False,"skipped":"no_focus_own_file"})
        print(f"  {txt!r}: SKIP (no enfoqué mi archivo)",flush=True); continue
    reg.execute("gui",{"action":"keypress","keys":"ctrl+end"});time.sleep(0.1)
    reg.execute("gui",{"action":"type_into","text":txt,"window":_NK});time.sleep(0.35)
    reg.execute("gui",{"action":"keypress","keys":"enter"});time.sleep(0.15)
    safe=txt.replace('"','')
    code=('import uiautomation as a\n'
          'f=False\n'
          'for w in a.GetRootControl().GetChildren():\n'
          ' if "'+_NK+'" in (w.Name or "").lower():\n'
          '  s=list(w.GetChildren());d=0\n'
          '  while s and d<600:\n'
          '   el=s.pop();d+=1\n'
          '   try:\n'
          '    vp=el.GetValuePattern();v=vp.Value or ""\n'
          '   except Exception:\n    v=el.Name or ""\n'
          '   if "'+safe.lower()+'" in (v or "").lower(): f=True;break\n'
          '   try: s.extend(el.GetChildren())\n'
          '   except Exception: pass\n'
          'print("YES" if f else "NO")')
    ok=_read_subproc(code)=="YES"
    results["notepad"].append({"text":txt,"ok":ok})
    print(f"  {txt!r}: {'OK' if ok else 'FAIL'}",flush=True)

out=ROOT/"scripts"/"gui_eval"/"_exhaustive_results.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
print("",flush=True)
for area,rows in results.items():
    n=sum(1 for r in rows if r.get("ok")); print(f">> {area}: {n}/{len(rows)}",flush=True)
print("WROTE",out,flush=True)
