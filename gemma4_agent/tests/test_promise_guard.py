"""Tests for the 'promise without action' guard and continuation-inherits-tools.

Real bug observed (2026-05-16, turn 16:53):
  user: "Prefiero cronologico" (continuation after web research about Batman Arkham)
  agent: tool_subset=[], no tool calls
  reply: "Listo, buscaré el orden cronológico..."  <- empty promise, user waits forever
"""
from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock


class _DummyTraceMixin:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def event(self, _turn_id, kind, **kw):
        self.events.append((kind, kw))

    def new_turn_id(self):
        return "test_turn"


class TestPromiseWithoutActionGuard(unittest.TestCase):
    """The guard rewrites empty promises so the user is not stranded."""

    def setUp(self):
        # We test the standalone method by binding it to a minimal stub.
        # The stub mirrors the subset of Gemma4Agent state that
        # _guard_promise_without_action and its callee
        # _build_user_facing_fallback actually read. Without the bound
        # method the guard hits AttributeError on the very first call.
        from gemma4_agent.agent_core.agent import Gemma4Agent
        self._guard = Gemma4Agent._guard_promise_without_action
        # _build_user_facing_fallback lives on Gemma4Agent — bind it
        # unbound to the stub so the stub.<method>(self_stub, …) shape
        # the guard expects works.
        self._stub = type("Stub", (), {
            "trace": _DummyTraceMixin(),
            "_build_user_facing_fallback": Gemma4Agent._build_user_facing_fallback,
            # State attributes _build_user_facing_fallback reads via
            # getattr(self, …, default). Defaults keep the streak logic
            # deterministic across tests.
            "_current_user_text": "",
            "_last_fallback_user_text": "",
            "_fallback_streak": 0,
            "_last_router_subset": [],
        })()

    def _run(self, content: str, events: list[Any]) -> str:
        return self._guard(self._stub, content, events)

    def test_replaces_empty_buscare(self):
        # "Buscaré ..." (sin prefijo false-confirm) dispara promise guard.
        out = self._run("Buscaré el orden cronológico para Batman.", [])
        self.assertNotIn("buscaré", out.lower())
        self.assertTrue(any(k == "promise_without_action_caught"
                            for k, _ in self._stub.trace.events))

    def test_replaces_te_proporcionare(self):
        out = self._run(
            "Listo, te proporcionaré el orden cronológico de los juegos.", [],
        )
        self.assertNotIn("proporcionar", out.lower())

    def test_replaces_voy_a_buscar(self):
        out = self._run("Voy a buscar esa información en internet.", [])
        self.assertNotIn("voy a buscar", out.lower())

    def test_english_promises(self):
        out = self._run("I'll search that for you.", [])
        self.assertNotIn("i'll search", out.lower())

    def test_does_nothing_when_tool_ran(self):
        events = [MagicMock(name="web_result")]
        original = "Listo, buscaré..."
        out = self._run(original, events)
        # If tool ran, the "promise" might just be narration around real result.
        self.assertEqual(out, original)

    def test_does_nothing_for_real_answer(self):
        original = "El orden cronológico es: Origins, Asylum, City, Knight."
        out = self._run(original, [])
        self.assertEqual(out, original)

    def test_strips_promise_from_long_reply(self):
        # If the reply has substantial content beyond the promise, the
        # promise sentence is removed but the rest is kept.
        long_reply = (
            "El orden cronológico es Origins (2013), Asylum (2009), "
            "City (2011) y Knight (2015). Voy a buscar también los DLC."
        )
        out = self._run(long_reply, [])
        # Real content preserved.
        self.assertIn("Origins", out)
        self.assertIn("Knight", out)
        # Promise sentence stripped.
        self.assertNotIn("voy a buscar", out.lower())

    def test_empty_input(self):
        out = self._run("", [])
        self.assertEqual(out, "")

    # ---- New patterns added in audit F-002 ----

    def test_replaces_te_aviso(self):
        out = self._run("Dame un rato, te aviso.", [])
        self.assertNotIn("te aviso", out.lower())

    def test_replaces_te_confirmo(self):
        out = self._run("Te confirmo en un minuto.", [])
        self.assertNotIn("te confirmo", out.lower())

    def test_replaces_te_paso(self):
        out = self._run("Listo, te paso el dato.", [])
        # "Listo," is a false-confirmation prefix, this should be caught.
        self.assertNotIn("te paso", out.lower())

    def test_replaces_dejame_ver(self):
        out = self._run("Déjame ver eso un momento.", [])
        self.assertNotIn("déjame ver", out.lower())

    def test_replaces_dejame_ver_no_accent(self):
        out = self._run("Dejame ver eso un momento.", [])
        self.assertNotIn("dejame ver", out.lower())

    def test_replaces_ya_te_digo(self):
        out = self._run("Esperá, ya te digo.", [])
        self.assertNotIn("ya te digo", out.lower())

    def test_replaces_te_explico(self):
        out = self._run("Te explico en un segundo.", [])
        self.assertNotIn("te explico", out.lower())

    # ---- False-confirmation patterns (audit F-002 sub-fix b) ----

    def test_false_confirmation_hecho_colon(self):
        out = self._run("Hecho: te agendé el evento.", [])
        self.assertEqual(
            out, "No alcancé a completar la acción. ¿La repetimos?",
        )
        self.assertTrue(any(k == "false_confirmation_caught"
                            for k, _ in self._stub.trace.events))

    def test_false_confirmation_listo_comma(self):
        out = self._run("Listo, registré tu rutina y la ejecuté.", [])
        self.assertEqual(
            out, "No alcancé a completar la acción. ¿La repetimos?",
        )

    def test_false_confirmation_ejecute(self):
        out = self._run("Ejecuté la búsqueda como pediste.", [])
        self.assertEqual(
            out, "No alcancé a completar la acción. ¿La repetimos?",
        )

    def test_false_confirmation_agende(self):
        out = self._run("Agendé el evento para mañana.", [])
        self.assertEqual(
            out, "No alcancé a completar la acción. ¿La repetimos?",
        )

    def test_false_confirmation_envie(self):
        out = self._run("Envié el mensaje a Juan.", [])
        self.assertEqual(
            out, "No alcancé a completar la acción. ¿La repetimos?",
        )

    def test_false_confirmation_not_triggered_when_tool_ran(self):
        # When a tool actually ran, the confirmation is real — don't rewrite.
        events = [MagicMock(name="whatsapp_result")]
        original = "Hecho: te agendé el evento."
        out = self._run(original, events)
        self.assertEqual(out, original)


if __name__ == "__main__":
    unittest.main()
