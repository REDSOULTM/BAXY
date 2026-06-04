"""Regression test for the window/app schemas re: "what's running NOW".

BUG real (log voz turno 14, 2026-06-03): "¿qué juego estoy jugando?" -> el 4B
eligió app(search, query="jugando") (buscó una APP llamada "jugando") en vez de
window(action="active") (la ventana en foco = el juego). Causa: el schema de
`window` no documentaba que `active` responde "qué app/juego está en foco" (todo
el texto era sobre `close`), y `app` no tenía nota negativa. Este test fija que:
  - window.active está documentado con ejemplos de pregunta de estado-local,
  - app advierte que NO es para saber qué está en foco (-> window.active).

Schemas list = COMPOUND_TOOL_SCHEMAS (TOOL_SCHEMAS no existe).
"""
from __future__ import annotations

import unittest

from gemma4_agent.tools_pkg.tool_schemas import COMPOUND_TOOL_SCHEMAS


def _desc(name: str) -> str:
    s = next((t for t in COMPOUND_TOOL_SCHEMAS
              if t.get("function", {}).get("name") == name), None)
    assert s is not None, f"{name} schema not found"
    return s["function"]["description"]


class WindowActiveSchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.window = _desc("window")
        self.app = _desc("app")

    def test_window_documents_active_foreground(self) -> None:
        # active() debe estar documentado como "ventana/app/juego en foco".
        self.assertIn("active()", self.window)
        low = self.window.lower()
        self.assertIn("foreground", low)

    def test_window_active_has_game_question_example(self) -> None:
        # Ejemplo canónico del bug: "¿qué juego estoy jugando?" -> window.active().
        self.assertIn("jugando", self.window)
        self.assertIn("window.active()", self.window)

    def test_window_active_multilingual_examples(self) -> None:
        # Multi-idioma (no overfit a español): EN + IT presentes.
        low = self.window.lower()
        self.assertIn("what game am i playing", low)
        self.assertIn("gioco", low)  # 'che gioco sto giocando?'

    def test_app_warns_not_for_foreground(self) -> None:
        # app debe desviar la pregunta de estado-local a window.active.
        low = self.app.lower()
        self.assertIn("window", low)
        self.assertTrue("foco" in low or "abierto ahora" in low or "open or in foco" in low,
                        "app schema must warn it's not for what's-running-now")
        # No debe sugerir pasar el verbo de la pregunta como query.
        self.assertIn("jugando", low)


if __name__ == "__main__":
    unittest.main()
