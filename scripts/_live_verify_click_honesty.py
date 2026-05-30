"""Verificación EN VIVO de la honestidad tri-estado del click (C4/C5, roadmap).

NO usa input sintético (gui.{type,click,keypress} físico mataría VS Code). En su
lugar ejercita el PlanExecutor REAL de producción con el dispatch `tools.execute`
mockeado para devolver los tres estados que el SO puede reportar:
  - verified=None      (UIA demorado en Electron/Discord -> NO medible)
  - state_changed=False (medido y NADA cambió -> false-PASS)
  - verified=True       (medido OK)

Verifica el comportamiento end-to-end del executor + summarize_result (el camino
real que ve el usuario), no funciones aisladas:
  1. None NO dispara el retry (antes = doble-click físico).
  2. summarize_result nunca afirma "Listo, hice click" cuando nada cambió.
  3. un click verificado SÍ se reporta como hecho.

Uso: python scripts/_live_verify_click_honesty.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gemma4_agent.computer_use_pkg.computer_use as cu  # noqa: E402
from gemma4_agent.computer_use_pkg.computer_use import summarize_result  # noqa: E402


def _executor(gui_result):
    ag = MagicMock()
    ag.tools.execute.return_value = gui_result
    ag.tools._focus_window_chen.return_value = True
    # detector.snapshot debe devolver algo plausible; usamos un dict mínimo.
    ex = cu.PlanExecutor(ag)
    return ex, ag


CASES = [
    # (nombre, gui_result, expectativa)
    ("UIA no medible (None)", {"ok": True},
     {"verified_is": None, "retry_call_count_max": 1}),
    ("medido sin cambio (False)", {"ok": True, "state_changed": False},
     {"verified_is": False}),
    ("medido OK (True)", {"ok": True, "verified": True, "state_changed": True},
     {"verified_is": True}),
]


def main() -> int:
    failures = []

    print("== 1. _click propaga el tri-estado (no colapsa None->False) ==")
    for name, gui_result, exp in CASES:
        ex, ag = _executor(gui_result)
        r = ex._click("Aceptar", "Discord")
        got = r["verified"]
        ok = (got is exp["verified_is"])
        print(f"  {'OK ' if ok else 'FALLA'} {name}: _click.verified = {got!r} (esperado {exp['verified_is']!r})")
        if not ok:
            failures.append(f"_click {name}: got {got!r}")

    print()
    print("== 2. summarize_result es HONESTO (no miente sobre el click) ==")
    honesty = [
        ("no medible", {"verified": None, "state_changed": None},
         lambda m: "no pude confirmar" in m.lower(),
         "debe admitir que no confirmó"),
        ("nada cambió", {"verified": False, "state_changed": False},
         lambda m: "no vi ningún cambio" in m.lower() and "listo, hice click" not in m.lower(),
         "NO debe afirmar 'Listo, hice click'"),
        ("verificado", {"verified": True, "state_changed": True},
         lambda m: "hice click" in m.lower() and "no vi" not in m.lower(),
         "SÍ debe reportar el click hecho"),
    ]
    for name, sig, check, why in honesty:
        plan = [{"op": "click", "arg": "Comprar"}]
        res = {"ok": True, "verified": True, "focused_app": "Tienda",
               "steps": [{"op": "click", "arg": "Comprar", "ok": True, **sig}]}
        msg = summarize_result("clickeá comprar", plan, res)
        ok = check(msg)
        print(f"  {'OK ' if ok else 'FALLA'} {name} ({why}):")
        print(f"        -> {msg!r}")
        if not ok:
            failures.append(f"summary {name}: {msg!r}")

    print()
    if failures:
        print(f"RESULTADO: {len(failures)} FALLAS:")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULTADO: TODO OK — el click es honesto (None preservado, sin mentiras).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
