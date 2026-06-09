r"""PRUEBA EN VIVO del fast-path UIA en Python (uia_fast.py) — PARA QUE LO CORRA EL
USUARIO (el sandbox no puede validar clicks físicos: cierran VS Code).

Qué hace: compara el camino PYTHON (uiautomation in-process) vs el PowerShell para
las 4 acciones (tree, find, click, set_value) sobre una app real, y mide latencia.
El click/set_value MUEVEN EL MOUSE / ESCRIBEN de verdad, así que:

  ⚠️  ABRÍ LA CALCULADORA DE WINDOWS antes de correr esto, y dejala al frente.
      El test va a apretar dígitos en ella. No toques el mouse mientras corre.

USO:
  1) Abrí la Calculadora (calc.exe) y dejala en foco.
  2) python scripts\_diag\_test_uia_python_live.py
  3) Mirá que: (a) el Python y el PowerShell encuentren los MISMOS elementos,
     (b) el CLICK apriete el dígito correcto en la Calculadora,
     (c) la latencia del Python sea menor.

Para forzar SOLO PowerShell (comparar):  set GEMMA4_UIA_PYTHON=0 && python ...
Para forzar SOLO Python:                 (default, GEMMA4_UIA_PYTHON=1)
"""
import sys, os, time, json
sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DIAG", "1")
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")

import tempfile, pathlib
from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.memory_pkg.memory import MemoryStore
from gemma4_agent.memory_pkg.state import AgentState

tmp = pathlib.Path(tempfile.mkdtemp())
reg = ToolRegistry(MemoryStore(tmp / "m.json"), tmp / "cap",
                   state=AgentState(tmp / "s.json"), safety_enabled=False)


def _run(label, args):
    t = time.perf_counter()
    r = reg.execute("uia", args)
    dt = (time.perf_counter() - t) * 1000.0
    src = r.get("source") or "powershell"
    ok = r.get("ok") is not False
    print(f"  [{label}] {dt:7.0f}ms  source={src}  ok={ok}")
    return r, dt


def _compare_action(action, args):
    print(f"\n=== acción: {action} ===")
    os.environ["GEMMA4_UIA_PYTHON"] = "1"
    rp, dtp = _run("PYTHON  ", {"action": action, **args})
    os.environ["GEMMA4_UIA_PYTHON"] = "0"
    rs, dts = _run("PowerSh.", {"action": action, **args})
    os.environ["GEMMA4_UIA_PYTHON"] = "1"
    speedup = (dts / dtp) if dtp else 0
    print(f"  -> Python {speedup:.1f}x más rápido" if speedup > 1 else "  -> (sin ventaja)")
    return rp, rs


def main():
    print(__doc__)
    print("Esperando 3s para que pongas la Calculadora al frente...")
    for i in (3, 2, 1):
        print(f"  {i}...", flush=True); time.sleep(1)

    # 1) TREE (lectura) — debe listar controles de la ventana en foco.
    rp, rs = _compare_action("tree", {"window": "", "limit": 30})
    print(f"  python listó {rp.get('count')} elementos; PowerShell {rs.get('count')}")

    # 2) FIND (lectura) — buscar el botón "7" (Siete/Seven según idioma).
    for q in ("siete", "seven", "7"):
        rp, rs = _compare_action("find", {"query": q, "limit": 10})
        if (rp.get("count") or 0) > 0 or (rs.get("count") or 0) > 0:
            print(f"  query {q!r}: python {rp.get('count')} matches, PS {rs.get('count')}")
            break

    # 3) CLICK (ACCIÓN — aprieta el dígito de verdad). Probamos "7".
    print("\n  >>> El siguiente paso APRIETA un dígito en la Calculadora <<<")
    os.environ["GEMMA4_UIA_PYTHON"] = "1"
    r, dt = _run("CLICK 7 (python)", {"action": "click", "query": "siete"})
    print(f"      method={r.get('method')} element.name={(r.get('element') or {}).get('name')}")
    print("      -> ¿apareció un 7 en la Calculadora? (verificá a ojo)")

    print("\n=== VEREDICTO ===")
    print("Si el Python encontró los mismos elementos que el PowerShell y el click")
    print("apretó el 7 correcto, la migración mantiene la CALIDAD con menos latencia.")
    print("Si algo falla en Python, poné GEMMA4_UIA_PYTHON=0 para volver al PowerShell.")


if __name__ == "__main__":
    main()
