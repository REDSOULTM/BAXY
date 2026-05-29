"""Red determinista de navegación (2026-05-27): cuando el 4B (E2B-Q4) NO emite
el tool-call de navegación ni forzado, el agente ejecuta browser.open directo si
la intención web es clara y hay URL extraíble. MEDIDO en vivo: github/youtube
pasaron de prosa-rara/silencio a "Listo, abrí X".

Mock-only: no LLM, no GUI. Mockeamos los clasificadores de intención y
tools.execute. Probamos el extractor de URL y _deterministic_navigate.
"""
from __future__ import annotations

import unittest
from unittest import mock

from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.agent_core.agent import Gemma4Agent, ToolEvent


def _agent():
    # Gemma4Agent real pero NO tocamos el LLM ni GUI en estos tests (solo
    # llamamos métodos puros / con tools.execute mockeado).
    return Gemma4Agent(AgentConfig.from_env())


class ExtractNavUrlTest(unittest.TestCase):
    def setUp(self):
        self.ag = _agent()

    def test_explicit_domain(self):
        self.assertEqual(self.ag._extract_nav_url("anda a github.com"),
                         "https://github.com")

    def test_explicit_https(self):
        self.assertEqual(self.ag._extract_nav_url("abri https://example.com/foo"),
                         "https://example.com/foo")

    def test_known_site_by_name(self):
        self.assertEqual(self.ag._extract_nav_url("entra a youtube"),
                         "https://www.youtube.com")
        self.assertEqual(self.ag._extract_nav_url("abri instagram"),
                         "https://www.instagram.com")

    def test_ambiguous_brand_no_guess(self):
        # "instant gaming" NO está en sitios conocidos y no trae TLD -> None
        # (no adivinamos .com vs .net; lo resuelve el flujo web-search).
        self.assertIsNone(self.ag._extract_nav_url("anda a instant gaming"))

    def test_not_a_domain_math(self):
        # "2+2" no debe parsear como dominio.
        self.assertIsNone(self.ag._extract_nav_url("calcula 2+2"))

    def test_no_target(self):
        self.assertIsNone(self.ag._extract_nav_url("hola como estas"))


class DeterministicNavigateTest(unittest.TestCase):
    def setUp(self):
        self.ag = _agent()

    def _patch_intents(self, nav=False, store=False):
        return (
            mock.patch("gemma4_agent.intent_router.wants_web_navigation", return_value=nav),
            mock.patch("gemma4_agent.intent_router.wants_web_store", return_value=store),
        )

    def test_navigates_when_intent_and_url(self):
        p1, p2 = self._patch_intents(nav=True)
        with p1, p2, mock.patch.object(self.ag.tools, "execute",
                                       return_value={"ok": True, "url": "https://github.com"}) as ex:
            ev = self.ag._deterministic_navigate("anda a github.com")
        self.assertIsInstance(ev, ToolEvent)
        self.assertEqual(ev.name, "browser")
        self.assertEqual(ev.args["action"], "open")
        self.assertEqual(ev.args["url"], "https://github.com")
        ex.assert_called_once()

    def test_no_navigate_when_not_web_intent(self):
        # intención NO es web -> no navega (aunque haya algo tipo URL).
        p1, p2 = self._patch_intents(nav=False, store=False)
        with p1, p2, mock.patch.object(self.ag.tools, "execute") as ex:
            ev = self.ag._deterministic_navigate("que es github.com")
        self.assertIsNone(ev)
        ex.assert_not_called()

    def test_no_navigate_when_no_extractable_url(self):
        # intención web pero marca ambigua sin TLD -> NO adivina -> None.
        p1, p2 = self._patch_intents(nav=True)
        with p1, p2, mock.patch.object(self.ag.tools, "execute") as ex:
            ev = self.ag._deterministic_navigate("anda a instant gaming")
        self.assertIsNone(ev)
        ex.assert_not_called()

    def test_store_intent_with_known_site(self):
        p1, p2 = self._patch_intents(store=True)
        with p1, p2, mock.patch.object(self.ag.tools, "execute",
                                       return_value={"ok": True, "url": "https://www.amazon.com"}):
            ev = self.ag._deterministic_navigate("compra algo en amazon")
        self.assertIsNotNone(ev)
        self.assertEqual(ev.args["url"], "https://www.amazon.com")


if __name__ == "__main__":
    unittest.main()
