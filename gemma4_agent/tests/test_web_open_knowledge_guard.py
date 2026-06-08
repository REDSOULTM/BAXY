"""web.open: guard conocimiento-vs-abrir (2026-06-08).

Regresión medida: "háblame de Mortal Kombat" -> el 4B hacía web.search (snippets
buenos) y LUEGO web.open de Wikipedia -> lanzaba un tab (que fallaba) en vez de
RESPONDER con los snippets. web.open lanza un navegador VISIBLE: solo tiene sentido
si el user quiere VER la página. Señal estructural de PROCEDENCIA (no keywords): si
el user NO dictó ese dominio en su texto, no pidió abrirlo -> redirigir a web.read
(trae contenido para responder). Si SÍ lo dictó -> open real.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.memory_pkg.memory import MemoryStore


class WebOpenKnowledgeGuardTest(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.reg = ToolRegistry(MemoryStore(tmp / "mem.json"), tmp / "cap")
        self.opened: list[str] = []
        self.read: list[str] = []
        self.reg.web_open_url = lambda a: (  # type: ignore[assignment]
            self.opened.append(a.get("url")),
            {"ok": True, "status": "dispatched", "_opened": True})[1]
        self.reg.web_read = lambda a: (  # type: ignore[assignment]
            self.read.append(a.get("url")),
            {"ok": True, "text": "contenido de la página", "status": "done"})[1]

    def test_knowledge_question_redirects_open_to_read(self):
        # el user preguntó (no dictó el dominio) -> NO abrir tab, leer contenido.
        self.reg._current_user_text = "Háblame de Mortal Kombat"
        r = self.reg.t_web({"action": "open",
                            "url": "https://en.wikipedia.org/wiki/Mortal_Kombat"})
        self.assertEqual(self.opened, [])          # NO abrió navegador
        self.assertEqual(len(self.read), 1)        # leyó la página
        self.assertEqual(r.get("redirected_from"), "web.open")
        self.assertTrue(r.get("text"))             # contenido para responder

    def test_user_dictated_domain_opens_for_real(self):
        # el user dictó el dominio -> intención explícita de VER -> open real.
        self.reg._current_user_text = "abrí wikipedia.org"
        self.reg.t_web({"action": "open", "url": "https://wikipedia.org"})
        self.assertEqual(self.opened, ["https://wikipedia.org"])
        self.assertEqual(self.read, [])

    def test_open_without_user_text_opens(self):
        # sin _current_user_text (CLI/tests) -> no rompe: abre normal.
        self.reg._current_user_text = ""
        self.reg.t_web({"action": "open", "url": "https://example.com"})
        self.assertEqual(self.opened, ["https://example.com"])


if __name__ == "__main__":
    unittest.main()
