"""Tri-estado HONESTO del click in-process (perfection roadmap C4/C5, Ola 1 #2).

CAUSA RAÍZ medida (repro: scripts/_diag/_repro_click_tristate.py):
`_uia_click_inproc` (la capa PRIMARIA de gui_click_button — la que corre primero
y resuelve la mayoría de los clicks: "12/12 calc, 10/10 Discord") emitía
`verified = (changed is True)`, coaccionando el estado NO-MEDIBLE (changed=None,
p.ej. UIA demorado en Electron / verify_after sin _before) a `verified=False`.

Efecto del bug:
  (a) el PlanExecutor veía `verified is False` -> reintentaba = DOBLE-CLICK físico
      sobre una acción que quizá YA funcionó (sólo no la pudimos medir).
  (b) la recuperación tri-estado de _click (computer_use.py:601) sólo restaura
      desde `verified is None`; con False nunca se activaba.

Fix: `_uia_click_inproc` propaga `changed` TAL CUAL como `verified` (True/False/
None), igual que las otras capas (PowerShell/OCR/recover_click) que nunca ponen
verified=False salvo state_changed=False.

Estos tests aíslan la fuente: mockean `uiautomation` (sin GUI física) y
`gui_verify.verify_after` para forzar cada estado de `changed` y verificar el
mapeo tri-estado. NO tocan la pantalla. NO arrancan el LLM.
"""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch


def _fake_uiautomation_module(control):
    """Módulo `uiautomation` falso cuyo GetRootControl devuelve un árbol con un
    único control hijo `control` (que matchea el label y expone InvokePattern)."""
    mod = types.ModuleType("uiautomation")

    class _Root:
        def GetChildren(self):
            # una "ventana" cuyo Name contiene el window-hint, con el control adentro
            win = MagicMock()
            win.Name = "Discord"
            win.GetChildren = lambda: [control]
            return [win]

    mod.GetRootControl = lambda: _Root()
    return mod


def _fake_control(label="Aceptar"):
    el = MagicMock()
    el.Name = label
    el.ControlTypeName = "ButtonControl"
    el.GetChildren = lambda: []
    ip = MagicMock()
    ip.Invoke = MagicMock()
    el.GetInvokePattern = lambda: ip
    return el


class ClickInprocTriStateTest(unittest.TestCase):
    def _run_inproc(self, changed):
        """Corre _uia_click_inproc con verify_after forzado a devolver `changed`."""
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        tools = ToolRegistry.__new__(ToolRegistry)  # sin __init__ (evita side-effects)
        el = _fake_control("Aceptar")
        fake_uia = _fake_uiautomation_module(el)
        with patch.dict(sys.modules, {"uiautomation": fake_uia}):
            with patch("gemma4_agent.computer_use_pkg.gui_verify.capture_before",
                       return_value={"roi": "x"}):
                with patch("gemma4_agent.computer_use_pkg.gui_verify.verify_after",
                           return_value={"state_changed": changed, "reason": "test"}):
                    with patch("gemma4_agent.tools_pkg.tools.gui_safety", MagicMock()):
                        return tools._uia_click_inproc("Aceptar", "Discord")

    def test_changed_true_is_verified_true(self):
        r = self._run_inproc(True)
        self.assertIsNotNone(r)
        self.assertIs(r["state_changed"], True)
        self.assertIs(r["verified"], True)

    def test_changed_false_is_verified_false(self):
        # medido y NADA cambió -> false-PASS atrapado (verified=False honesto).
        r = self._run_inproc(False)
        self.assertIs(r["state_changed"], False)
        self.assertIs(r["verified"], False)

    def test_changed_none_stays_none_not_false(self):
        # NO MEDIBLE (UIA demorado/verify_after sin señal). El bug coaccionaba a
        # False; ahora debe quedar None para no gatillar el doble-click ni mentir.
        r = self._run_inproc(None)
        self.assertIsNone(r["state_changed"])
        self.assertIsNone(r["verified"], "no-medible debe quedar None, no False")


if __name__ == "__main__":
    unittest.main()
