"""Regression tests for the false-confirmation guard interaction with
phrase-triggered routines (Bug observed 2026-05-16 21:23).

Symptom: user said "tiempo" which fires a phrase trigger that pauses music
pre-LLM. The agent's reply began with "Listo, ..." (legitimate confirmation
of that real pre-LLM action). But tool_events was empty (routines don't
register as LLM-issued tool_calls), so the false-confirmation guard
replaced the reply with "No alcancé a completar la acción".

Fix: both `_guard_promise_without_action` and `_guard_grounded_action_claim`
must SKIP the check when `self._phrase_fires` is non-empty.
"""
from __future__ import annotations

import inspect
import unittest


class TestGuardsRespectPhraseFires(unittest.TestCase):

    def test_promise_guard_skips_when_phrase_fires(self):
        from gemma4_agent.agent_core.agent import Gemma4Agent
        src = inspect.getsource(Gemma4Agent._guard_promise_without_action)
        self.assertIn("_phrase_fires", src,
                      "guard must check self._phrase_fires")

    def test_grounding_gate_skips_when_phrase_fires(self):
        from gemma4_agent.agent_core.agent import Gemma4Agent
        src = inspect.getsource(Gemma4Agent._guard_grounded_action_claim)
        self.assertIn("_phrase_fires", src,
                      "grounding gate must check self._phrase_fires")


class TestPromiseGuardFunctionalSkip(unittest.TestCase):
    """Functional: a stub with phrase_fires set should NOT have its 'Listo'
    reply replaced.
    """

    def test_listo_reply_with_phrase_fires_is_preserved(self):
        from gemma4_agent.agent_core.agent import Gemma4Agent

        class _T:
            def __init__(self):
                self.events = []

            def event(self, *a, **kw):
                self.events.append((a, kw))

            def new_turn_id(self):
                return "t"

        stub = type("S", (), {})()
        stub.trace = _T()
        stub._phrase_fires = [{"label": "pausa_musica", "results": [{"ok": True}]}]
        reply = "Listo, la reproducción de música se ha pausado."
        out = Gemma4Agent._guard_promise_without_action(stub, reply, [])
        self.assertEqual(out, reply,
                         "reply must be preserved when a phrase trigger fired")


class TestStreamingBringsBrowserToFront(unittest.TestCase):
    """After successful play, the agent should issue a window focus call so
    the browser comes to the foreground (and gets auto-maximized if small).
    """

    def test_streaming_cdp_play_has_bring_to_front_helper(self):
        from gemma4_agent import domain_tools
        src = inspect.getsource(domain_tools._streaming_cdp_play)
        self.assertIn("_bring_browser_to_front", src)
        self.assertIn('action": "focus"', src)


if __name__ == "__main__":
    unittest.main()
