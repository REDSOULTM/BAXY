"""Tests for detect_leaked_tool_call (the rescue parser for tool calls
that the LLM emits as plain text instead of via the native mechanism).

Real cases observed in production logs (2026-05-16, turn 16:39-16:40):
  - Gemma replied 'web(action="search", query="de que trata GTA 5")'
    instead of emitting a tool_call. tool_events=0, the user saw the
    raw call as the chat message.
"""
from __future__ import annotations

import json
import unittest

from .reasoning import detect_leaked_tool_call


KNOWN = {"web", "media", "browser", "whatsapp", "memory", "steam", "system"}


class TestRescueRealLeaks(unittest.TestCase):

    def test_web_kwargs_leak(self):
        out = detect_leaked_tool_call(
            'web(action="search", query="de que trata GTA 5")',
            known_tool_names=KNOWN,
        )
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "web")
        args = json.loads(out["function"]["arguments"])
        self.assertEqual(args["action"], "search")
        self.assertEqual(args["query"], "de que trata GTA 5")

    def test_media_single_dict_positional_arg(self):
        out = detect_leaked_tool_call(
            'media({"action": "play", "provider": "disney", "query": "Loki"})',
            known_tool_names=KNOWN,
        )
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "media")
        args = json.loads(out["function"]["arguments"])
        self.assertEqual(args["provider"], "disney")
        self.assertEqual(args["query"], "Loki")

    def test_browser_multi_kwargs(self):
        out = detect_leaked_tool_call(
            'browser(action="search", browser="Opera", engine="google", query="Doom")',
            known_tool_names=KNOWN,
        )
        self.assertIsNotNone(out)
        args = json.loads(out["function"]["arguments"])
        self.assertEqual(args["browser"], "Opera")
        self.assertEqual(args["query"], "Doom")

    def test_single_quote_kwargs(self):
        out = detect_leaked_tool_call(
            "whatsapp(action='send', to='Juan', text='hola que tal')",
            known_tool_names=KNOWN,
        )
        self.assertIsNotNone(out)
        args = json.loads(out["function"]["arguments"])
        self.assertEqual(args["to"], "Juan")

    def test_narrated_call(self):
        out = detect_leaked_tool_call(
            'Voy a buscar web(action="search", query="X") en internet',
            known_tool_names=KNOWN,
        )
        # Match the trailing call even when narrated.
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "web")


class TestRescueRejectsCleanText(unittest.TestCase):
    """Falsos positivos: prose normal con paréntesis NO debe disparar."""

    def test_normal_reply_with_parens(self):
        out = detect_leaked_tool_call(
            "GTA V (2013) salió en septiembre.",
            known_tool_names=KNOWN,
        )
        self.assertIsNone(out)

    def test_smalltalk(self):
        out = detect_leaked_tool_call(
            "Hola, ¿cómo estás?",
            known_tool_names=KNOWN,
        )
        self.assertIsNone(out)

    def test_confirmation_reply(self):
        out = detect_leaked_tool_call(
            "Listo, Loki reproduciéndose en Disney+.",
            known_tool_names=KNOWN,
        )
        self.assertIsNone(out)

    def test_parens_with_recommendation(self):
        out = detect_leaked_tool_call(
            "Te recomiendo (si tienes tiempo) que pruebes esto.",
            known_tool_names=KNOWN,
        )
        self.assertIsNone(out)

    def test_empty_content(self):
        self.assertIsNone(detect_leaked_tool_call("", known_tool_names=KNOWN))
        self.assertIsNone(detect_leaked_tool_call(None, known_tool_names=KNOWN))  # type: ignore[arg-type]

    def test_unknown_tool_name_rejected(self):
        # Looks like a call but the name is not a registered tool.
        out = detect_leaked_tool_call(
            'foobar(action="x")',
            known_tool_names=KNOWN,
        )
        self.assertIsNone(out)


class TestRescueOutputShape(unittest.TestCase):
    """El output debe ser compatible con la shape OpenAI tool_call."""

    def test_output_has_required_keys(self):
        out = detect_leaked_tool_call(
            'web(action="search", query="x")',
            known_tool_names=KNOWN,
        )
        assert out is not None
        self.assertIn("id", out)
        self.assertTrue(out["id"].startswith("call_"))
        self.assertEqual(out["type"], "function")
        self.assertIn("function", out)
        self.assertIn("name", out["function"])
        # arguments is a JSON-encoded string (per OpenAI spec).
        self.assertIsInstance(out["function"]["arguments"], str)
        # And it parses as valid JSON.
        json.loads(out["function"]["arguments"])

    def test_unicode_preserved(self):
        out = detect_leaked_tool_call(
            'web(action="search", query="qué es Daredevil Born Again")',
            known_tool_names=KNOWN,
        )
        assert out is not None
        args = json.loads(out["function"]["arguments"])
        self.assertIn("é", args["query"])


class TestRescueMultiCallPicksFirst(unittest.TestCase):
    """F-007: cuando el LLM emite multiples tool calls en un mismo reply,
    el rescue parser debe rescatar la PRIMERA que matchee known_tool_names
    (antes rescataba la ultima, perdiendo la llamada principal).
    """

    def test_multi_call_picks_first(self):
        out = detect_leaked_tool_call(
            'Primero web(action="search", query="A"). Luego whatsapp(to="X", text="hola")',
            known_tool_names=KNOWN,
        )
        self.assertIsNotNone(out)
        # La primera debe ser 'web', no 'whatsapp'.
        self.assertEqual(out["function"]["name"], "web")
        args = json.loads(out["function"]["arguments"])
        self.assertEqual(args["query"], "A")

    def test_multi_call_skips_unknown_then_picks_known(self):
        out = detect_leaked_tool_call(
            'Voy a unknown_tool(x=1) y despues web(action="search", query="B")',
            known_tool_names=KNOWN,
        )
        self.assertIsNotNone(out)
        # unknown_tool no esta en KNOWN, se debe saltear; web es el rescue.
        self.assertEqual(out["function"]["name"], "web")
        args = json.loads(out["function"]["arguments"])
        self.assertEqual(args["query"], "B")


if __name__ == "__main__":
    unittest.main()
