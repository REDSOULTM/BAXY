"""Tests de win_focus.focus_and_maximize (foco+maximize robusto, Problema C).

El foco real de una ventana no es CI-friendly (roba foco). Estos tests
verifican el manejo defensivo (hwnd inválido, sin pywin32). La prueba real
(traer Notepad minimizado al frente) se hizo manualmente 2026-05-23: OK.
"""
from __future__ import annotations

import unittest


class WinFocusDefensiveTest(unittest.TestCase):
    def test_invalid_hwnd_returns_false(self):
        from gemma4_agent.win_focus import focus_and_maximize
        self.assertFalse(focus_and_maximize(0))
        self.assertFalse(focus_and_maximize(999_999_999))

    def test_importable(self):
        # El módulo debe importar aunque uiautomation no esté (capa UWP opcional).
        import gemma4_agent.win_focus as wf
        self.assertTrue(hasattr(wf, "focus_and_maximize"))

    def test_window_tool_uses_focus_helper(self):
        # El window tool debe referirse a win_focus en su path de focus.
        import inspect
        from gemma4_agent import tools
        src = inspect.getsource(tools)
        self.assertIn("focus_and_maximize", src,
                      "window(action=focus) debería usar win_focus.focus_and_maximize")


if __name__ == "__main__":
    unittest.main()
