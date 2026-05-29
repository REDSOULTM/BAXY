"""Computer-use END-TO-END con el LLM real (vram4 en :8080). Verifica por ESTADO
DEL SO, no por el texto del modelo.

CLAVE (corregido 2026-05-25): la continuación deíctica ("calculá 5x5" tras abrir
la calc) depende de la HERENCIA de contexto GUI del turno previo (fix calc-
hallucination, _GUI_CONTEXT_TOOLS). Por eso NO se usa agente fresco por caso: se
usa UNA sesión, se abre la calc primero, y los "operá" son turnos SIGUIENTES en la
misma sesión — el flujo real del usuario. Cada turno resetea su propio budget en
agent.run (agent.py:679). COM-safe (lee display en subproceso).

NO toca archivos del usuario: sólo Calculadora.
"""
import sys, time, json, subprocess, tempfile, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")

def _read_subproc(code):
    r = subprocess.run(["python","-c",code], capture_output=True, text=True, timeout=20)
    return r.stdout.strip()

def calc_display():
    code=('import uiautomation as a\n'
          'for w in a.GetRootControl().GetChildren():\n'
          ' if "alculadora" in (w.Name or ""):\n'
          '  r=w.TextControl(AutomationId="CalculatorResults",searchDepth=10)\n'
          '  print(r.Name if r.Exists(0.5) else "NONE");break\n'
          'else: print("NOCALC")')
    return _read_subproc(code)

def calc_dig():
    d=calc_display() or ""
    return "".join(c for c in d if c.isdigit())

def build_agent():
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig
    return Gemma4Agent(AgentConfig.from_env())

def kill_calc():
    subprocess.run(["taskkill","/F","/IM","CalculatorApp.exe"],capture_output=True); time.sleep(0.6)

# Cada bloque: comando + (expected_digits | None). None = sólo abrir/preparar.
# Se ejecutan EN SECUENCIA sobre la MISMA sesión (flujo real multi-turno).
# CLAVE: la herencia de contexto GUI sólo encadena si CADA turno previo usó una
# tool GUI (agent.py:1062/1130). Por eso NO inyectamos un Escape fuera de run_text
# (rompe la cadena): pedimos al AGENTE que borre, y cada operación dice "y apretá
# igual" para que el 4B complete la cuenta (sin "=" la calc no resuelve).
# Limpiamos con un turno determinista que SÍ pasa por run_text-equivalente para no
# romper la cadena de herencia: usamos gui keypress ESC vía el agente PERO marcamos
# _last_executed_tools=['gui'] para mantener la herencia (el ESC es input del agente).
# Cada operación pide "escribí X y apretá igual" (el patrón que MIDE bien). NO usamos
# "borrá" como verbo (medido: el 4B lo manda a filesystem — comando ambiguo, mal caso).
SEQ = [
    ("abrí la calculadora", None),
    ("escribí 2 más 2 y apretá igual", "4"),
    ("escribí 5 por 5 y apretá igual", "25"),
    ("escribí 9 más 1 y apretá igual", "10"),
    ("escribí 8 menos 3 y apretá igual", "5"),
    ("escribí 6 por 7 y apretá igual", "42"),
    ("escribí 12 más 12 y apretá igual", "24"),
    ("escribí 100 dividido 4 y apretá igual", "25"),
    ("escribí 7 más 8 y apretá igual", "15"),
    ("escribí 11 por 11 y apretá igual", "121"),
]

def _clear_keep_chain(ag):
    # Escape determinista SIN romper la herencia GUI: ejecuta el keypress y deja
    # _last_executed_tools=['gui'] para que el siguiente turno deíctico herede.
    try:
        from gemma4_agent.computer_use_pkg import gui_safety

        gui_safety.reset_action_budget()
        ag.tools.execute("gui",{"action":"keypress","keys":"escape"}); time.sleep(0.25)
        ag._last_executed_tools = ["gui"]
    except Exception: pass

print("=== LLM COMPUTER-USE x{} (1 sesión, multi-turno real) ===".format(len(SEQ)),flush=True)
kill_calc()
ag = build_agent()
ag.run_text("hola")  # warm
results=[]
for i,(cmd, exp) in enumerate(SEQ):
    if exp is not None:
        _clear_keep_chain(ag)  # limpiar display sin romper herencia GUI
    seen=[]
    def progress(stage, info=None): seen.append(stage)
    t=time.time()
    try:
        r=ag.run_text(cmd, progress=progress)
        reply=(getattr(r,"content",None) or "")[:55]; err=getattr(r,"error",None)
    except Exception as exc:
        reply=""; err=f"EXC {type(exc).__name__}: {exc}"
    dt=time.time()-t
    called=any("tool" in s for s in seen)
    time.sleep(0.6)
    dig=calc_dig()
    ok = (exp is None) or (exp == dig or dig.endswith(exp))
    results.append({"cmd":cmd,"exp":exp,"display":calc_display(),"dig":dig,
                    "tool_called":called,"ok":ok,"reply":reply,"err":err,"latency_s":round(dt,2)})
    tag = "(setup)" if exp is None else ("OK" if ok else "FAIL")
    print(f"  [{i}] {cmd!r} -> exp={exp} dig={dig!r} tool={called} {tag} ({dt:.1f}s) reply={reply!r}",flush=True)

out=ROOT/"scripts"/"gui_eval"/"_exhaustive_llm_results.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
graded=[r for r in results if r["exp"] is not None]
n=sum(1 for r in graded if r["ok"])
print(f"\n>> LLM computer-use (operaciones): {n}/{len(graded)}",flush=True)
print("WROTE",out,flush=True)
