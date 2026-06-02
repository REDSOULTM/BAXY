"""Repro del false-PASS de click (C4/C5, perfection roadmap Ola 1 #2).

Reproduce SIN GUI física: simula los resultados crudos que las distintas
capas de gui_click_button producen, los pasa por PlanExecutor._click y por
summarize_result, y mide cuántas veces el sistema:
  (a) afirma exito con state_changed=False (false-PASS) -> debe ser 0
  (b) coacciona None (no-medible) a False (gatilla doble-click) -> debe ser 0

NO toca la pantalla. NO arranca el LLM. Solo lógica pura.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import gemma4_agent.computer_use_pkg.computer_use as cu  # noqa: E402
from gemma4_agent.computer_use_pkg.computer_use import summarize_result  # noqa: E402


def _executor(gui_result):
    ag = MagicMock()
    ag.tools.execute.return_value = gui_result
    return cu.PlanExecutor(ag)


# Resultados CRUDOS tal como cada capa de gui_click_button los emite HOY.
# Fuente: tools.py
#   - _uia_click_inproc:6589 -> {"ok": invoked, "state_changed": changed, "verified": changed is True}
#       changed puede ser None (no medible), False (medido sin cambio), True.
#   - gui_click_button:6435/6450 -> state_changed anotado; verified=False solo si False.
#   - _click_button_via_ocr / _recover_click: similar.
RAW_CASES = [
    # (nombre, raw_result_de_la_capa)
    # IN-PROCESS (primary path). POST-FIX: changed=None -> verified=None (tri-estado
    # honesto). ANTES del fix esto era verified=False (None coaccionado), que es el
    # bug que cierra esta tarea. Para ver el bug histórico cambiar la 1ra línea a
    # {"ok": True, "state_changed": None, "verified": False}.
    ("inproc_changed_none",  {"ok": True, "state_changed": None,  "verified": None}),
    ("inproc_changed_false", {"ok": True, "state_changed": False, "verified": False}),
    ("inproc_changed_true",  {"ok": True, "state_changed": True,  "verified": True}),
    # PowerShell/coord path — no setea verified salvo en el caso False.
    ("ps_changed_none",      {"ok": True, "state_changed": None}),
    ("ps_changed_false",     {"ok": True, "state_changed": False, "verified": False,
                              "completion_status": "clicked_no_effect"}),
    ("ps_changed_true",      {"ok": True, "state_changed": True}),
    # Sin medicion alguna (UIA crash en verify_after).
    ("no_signal",            {"ok": True}),
]


def classify(raw):
    """Pasa el raw por _click y summarize_result; devuelve (verified, msg)."""
    ex = _executor(raw)
    # gui_click_button devuelve {"result": ...} en algunos paths; _click hace
    # inner = r.get("result", r). Probamos el caso directo (sin wrapper) que es
    # el que devuelven inproc/ps en este harness.
    step = ex._click("Aceptar", "Discord")
    plan = [{"op": "click", "arg": "Aceptar"}]
    res = {"ok": True, "verified": step["verified"] is True, "focused_app": "Discord",
           "steps": [{"op": "click", "arg": "Aceptar", **step}]}
    msg = summarize_result("clickeá aceptar", plan, res)
    return step["verified"], step.get("state_changed"), msg


def main():
    false_pass = 0   # afirma exito pero state_changed=False
    none_as_false = 0  # no-medible (changed None) terminó en verified=False
    total_change_unknown = 0  # cuantos casos son realmente "no se" (changed None/ausente)
    print(f"{'case':24} {'verified':10} {'state_chg':10} reply")
    print("-" * 100)
    for name, raw in RAW_CASES:
        verified, sc, msg = classify(raw)
        lower = msg.lower()
        claims_success = ("hice click" in lower or "listo" in lower) and \
                         "no vi" not in lower and "no pude confirmar" not in lower
        # ¿el raw indica que NO sabemos? (changed None o ausente)
        raw_unknown = raw.get("state_changed") is None
        if raw_unknown and verified is False:
            none_as_false += 1
        if raw_unknown:
            total_change_unknown += 1
        if raw.get("state_changed") is False and claims_success:
            false_pass += 1
        flag = ""
        if raw_unknown and verified is False:
            flag = "  <-- None coaccionado a False (gatilla doble-click)"
        if raw.get("state_changed") is False and claims_success:
            flag += "  <-- FALSE-PASS (miente exito)"
        print(f"{name:24} {str(verified):10} {str(sc):10} {msg[:55]!r}{flag}")
    print("-" * 100)
    n = len(RAW_CASES)
    print(f"\nGATE 1 false-PASS (exito con state_changed=False): {false_pass}/{n}  (meta 0)")
    print(f"GATE 2 None coaccionado a False (no-medible tratado como fallo): "
          f"{none_as_false}/{total_change_unknown} casos no-medibles")
    fp_rate = 100.0 * false_pass / n
    print(f"\nfalse-PASS rate global GUI: {fp_rate:.1f}%  (meta <2%, baseline roadmap 14.3%)")
    return false_pass, none_as_false


if __name__ == "__main__":
    main()
