"""Harness exhaustivo de gui_click_button (cascada in-proc UIA + foreground-safe).
Mide por ESTADO DEL SO: clickea botones NOMBRADOS de la Calculadora (UIA-estable,
locale ES) y verifica el display. COM-safe (lee display en subproceso). Resetea el
presupuesto de acciones por CASO (= turno de voz en prod, agent.py:679)."""
import sys, time, json, subprocess, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.memory_pkg.memory import MemoryStore
from gemma4_agent.computer_use_pkg import gui_safety


tmp = Path(tempfile.mkdtemp())
reg = ToolRegistry(memory=MemoryStore(tmp/"m.json"), captures_dir=tmp)

def _read_subproc(code):
    r = subprocess.run(["python","-c",code], capture_output=True, text=True, timeout=20)
    return r.stdout.strip()

def calc_display():
    code=('import uiautomation as a\n'
          'for w in a.GetRootControl().GetChildren():\n'
          ' if "alculadora" in (w.Name or ""):\n'
          '  r=w.TextControl(AutomationId="CalculatorResults",searchDepth=10)\n'
          '  print(r.Name if r.Exists(0.5) else "NONE");break')
    return _read_subproc(code)

def ensure_calc():
    n=_read_subproc('import uiautomation as a;print(sum(1 for w in a.GetRootControl().GetChildren() if "alculadora" in (w.Name or "")))')
    if n=="0" or not n:
        subprocess.Popen(["calc.exe"]); time.sleep(2.5)

def clear():
    gui_safety.reset_action_budget()
    reg.execute("gui",{"action":"keypress","keys":"escape"}); time.sleep(0.15)

# Cada caso: una SECUENCIA de clicks por NOMBRE de botón -> resultado esperado.
# Esto ejerce gui_click_button (cascada in-proc) end-to-end, no keypress.
CASES = [
    (["Dos","Más","Dos","Es igual a"], "4"),
    (["Cinco","Más","Tres","Es igual a"], "8"),
    (["Siete","Multiplicar por","Seis","Es igual a"], "42"),
    (["Nueve","Multiplicar por","Nueve","Es igual a"], "81"),
    (["Ocho","Menos","Tres","Es igual a"], "5"),
    (["Cuatro","Más","Cinco","Es igual a"], "9"),
    (["Seis","Multiplicar por","Siete","Es igual a"], "42"),
    (["Uno","Más","Uno","Es igual a"], "2"),
    (["Dos","Multiplicar por","Ocho","Es igual a"], "16"),
    (["Tres","Más","Cuatro","Es igual a"], "7"),
]

ensure_calc()
# warm-up descartado: el 1er click tras lanzar la app a veces corre antes de que
# el árbol UIA/ventana se asiente (no es del agente; la calc ya está caliente en
# uso real). Una secuencia de descarte estabiliza la medición.
gui_safety.reset_action_budget()
reg.execute("gui",{"action":"click_button","label":"Uno","window":"Calculadora"}); time.sleep(0.3)
clear()
results=[]; print("=== CALC click_button x10 (cascada in-proc) ===",flush=True)
for seq, exp in CASES:
    clear()
    gui_safety.reset_action_budget()   # turno nuevo para la secuencia entera
    gui_safety.set_turn_goal("calculá con los botones")
    all_ok=True; grounding=None
    for label in seq:
        r=reg.execute("gui",{"action":"click_button","label":label,"window":"Calculadora"})
        grounding=r.get("grounding")
        if not r.get("ok"): all_ok=False; break
        time.sleep(0.12)
    time.sleep(0.35)
    d=calc_display() or ""; dig="".join(c for c in d if c.isdigit())
    ok = all_ok and (exp == dig or dig.endswith(exp))
    results.append({"seq":" ".join(seq),"exp":exp,"display":d,"grounding":grounding,"ok":ok})
    print(f"  {' '.join(seq)} => {exp}: {d!r} g={grounding} {'OK' if ok else 'FAIL'}",flush=True)

out=ROOT/"scripts"/"gui_eval"/"_exhaustive_click_results.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
n=sum(1 for r in results if r["ok"])
print(f"\n>> click_button: {n}/{len(results)}",flush=True)
print("WROTE",out,flush=True)
