"""Red de honestidad: "¿Steam está abierto?" NO debe ABRIR Steam ni mentir.

BUG real (eval run2, 2026-06-04): el 4B elegía steam(open) ante "¿Steam está
abierto?" (aunque el router NO ofreciera steam, llegaba por forced-retry/schema)
-> abría Steam y respondía "Listo, abrí Steam" = MENTIRA + acción NO pedida sobre
una pregunta read-only. Fix B (tools.t_steam): si el texto del turno es una
pregunta de estado (_is_app_state_check), reportar si el proceso corre, NO abrir.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.memory_pkg.memory import MemoryStore
from gemma4_agent.memory_pkg.state import AgentState


def _reg() -> ToolRegistry:
    tmp = Path(tempfile.mkdtemp(prefix="gemma4_steam_"))
    return ToolRegistry(MemoryStore(tmp / "m.json"), tmp / "cap",
                        state=AgentState(tmp / "s.json"), safety_enabled=False)


class SteamStateHonestyTest(unittest.TestCase):
    def test_state_question_does_not_open_steam(self):
        reg = _reg()
        for q in ("revisa si Steam está abierto", "Steam está cerrado?",
                  "is Steam running?", "fijate si Steam está corriendo"):
            reg._current_user_text = q
            r = reg.t_steam({"action": "open"})
            self.assertEqual(r.get("completion_status"), "reported_state_did_not_open",
                             msg=f"{q!r} no debería abrir Steam")
            self.assertNotIn("uri", r, msg=f"{q!r} disparó steam://open")
            self.assertIn("running", r)

    def test_genuine_open_still_opens(self):
        # No-regresión: "abrí Steam" (acción real) SÍ abre.
        reg = _reg()
        reg._current_user_text = "abrí Steam"
        r = reg.t_steam({"action": "open"})
        # action open real -> uri presente (o al menos NO el short-circuit de estado)
        self.assertNotEqual(r.get("completion_status"), "reported_state_did_not_open")

    def test_no_user_text_is_noop(self):
        # Sin _current_user_text plumeado (tests/CLI viejos) -> comportamiento previo.
        reg = _reg()
        r = reg.t_steam({"action": "open"})
        self.assertNotEqual(r.get("completion_status"), "reported_state_did_not_open")

    def test_browser_state_question_does_not_open(self):
        # Mismo patrón que steam: "¿Chrome está abierto?" NO debe abrir el navegador.
        reg = _reg()
        for q in ("revisa si Chrome está abierto", "is Firefox running?",
                  "¿está abierto el navegador?"):
            reg._current_user_text = q
            r = reg.t_browser({"action": "open", "browser": "Chrome"})
            self.assertEqual(r.get("completion_status"), "reported_state_did_not_open",
                             msg=f"{q!r} no debería abrir el navegador")
            self.assertIn("running", r)

    def test_browser_open_with_url_still_opens(self):
        # No-regresión: abrir una URL real NO se intercepta (aunque el texto sea
        # una pregunta, lo que manda es que hay url/query concreta).
        reg = _reg()
        reg._current_user_text = "abrí youtube.com"
        r = reg.t_browser({"action": "open", "url": "youtube.com"})
        self.assertNotEqual(r.get("completion_status"), "reported_state_did_not_open")

    def test_howto_does_not_delete(self):
        # BUG real (cacería tanda 1): "cómo elimino una carpeta" -> filesystem.delete
        # BORRABA la carpeta ante una PREGUNTA. El handler rechaza el delete si el
        # texto del turno es una pregunta how-to.
        reg = _reg()
        reg._current_user_text = "cómo elimino una carpeta de pruebas"
        r = reg.filesystem_delete({"path": "C:/no/importa", "recursive": True})
        self.assertEqual(r.get("completion_status"), "howto_not_executed")

    def test_imperative_delete_not_intercepted_by_howto_guard(self):
        # No-regresión: un imperativo real NO es interceptado por el guard how-to
        # (cae al flujo normal de delete -> error por path inexistente, no al guard).
        reg = _reg()
        reg._current_user_text = "borrá la carpeta vieja"
        r = reg.filesystem_delete({"path": "C:/ruta/que/no/existe/zzz", "recursive": False})
        self.assertNotEqual(r.get("completion_status"), "howto_not_executed")


if __name__ == "__main__":
    unittest.main()
