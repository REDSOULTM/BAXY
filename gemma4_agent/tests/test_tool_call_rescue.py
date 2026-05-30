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

from ..support.reasoning import detect_leaked_tool_call


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


class TestRescueGemmaJsonForm(unittest.TestCase):
    """Sprint 8 (2026-05-20): Gemma 4 sometimes leaks tool calls in its
    native JSON shape (not the python-function shape), which the
    llama-server parser fails to lift into tool_calls. These must be
    rescued too. Formats documented in llama.cpp #21384 / mlx-lm #1096.
    """

    def test_bare_json(self):
        out = detect_leaked_tool_call(
            '{"name": "steam", "arguments": {"action": "open"}}',
            known_tool_names=KNOWN,
        )
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "steam")
        self.assertEqual(json.loads(out["function"]["arguments"])["action"], "open")

    def test_tool_call_markers(self):
        out = detect_leaked_tool_call(
            '<|tool_call>{"name": "steam", "arguments": {"action": "open"}}<tool_call|>',
            known_tool_names=KNOWN,
        )
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "steam")

    def test_fenced_tool_call_block(self):
        out = detect_leaked_tool_call(
            '```tool_call\n{"name": "media", "arguments": '
            '{"action": "play", "provider": "disney", "query": "daredevil"}}\n```',
            known_tool_names=KNOWN,
        )
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "media")
        self.assertEqual(json.loads(out["function"]["arguments"])["provider"], "disney")

    def test_fenced_json_with_parameters_key(self):
        out = detect_leaked_tool_call(
            '```json\n{"name": "web", "parameters": {"action": "search", "query": "x"}}\n```',
            known_tool_names=KNOWN,
        )
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "web")
        self.assertEqual(json.loads(out["function"]["arguments"])["query"], "x")

    def test_arguments_as_json_string(self):
        out = detect_leaked_tool_call(
            '{"name": "steam", "arguments": "{\\"action\\": \\"open\\"}"}',
            known_tool_names=KNOWN,
        )
        self.assertIsNotNone(out)
        self.assertEqual(json.loads(out["function"]["arguments"])["action"], "open")

    def test_json_with_narration_prefix(self):
        out = detect_leaked_tool_call(
            'Voy a abrir Steam: {"name": "steam", "arguments": {"action": "open"}}',
            known_tool_names=KNOWN,
        )
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "steam")

    def test_unknown_tool_json_rejected(self):
        out = detect_leaked_tool_call(
            '{"name": "notatool", "arguments": {}}',
            known_tool_names=KNOWN,
        )
        self.assertIsNone(out)

    def test_prose_with_braces_not_a_call(self):
        out = detect_leaked_tool_call(
            "me gusta el formato {clave: valor} en mis notas",
            known_tool_names=KNOWN,
        )
        self.assertIsNone(out)


class TestDottedMethodRescue(unittest.TestCase):
    """The model sometimes writes a compound tool's ACTION as a Python method
    — window.close(query="x") instead of window(action="close", query="x").
    Live repro 2026-05-20: "schliesse das Fenster" leaked window.close(...) as
    text and the window never closed. The rescue must rewrite it."""

    DOTTED_KNOWN = {"window", "app", "audio", "media", "steam", "web"}

    def test_dotted_close_with_single_quotes(self):
        out = detect_leaked_tool_call(
            "window.close(query='das Fenster')", known_tool_names=self.DOTTED_KNOWN)
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "window")
        args = json.loads(out["function"]["arguments"])
        self.assertEqual(args["action"], "close")
        self.assertEqual(args["query"], "das Fenster")

    def test_dotted_set_volume(self):
        out = detect_leaked_tool_call(
            "audio.set_volume(level=20)", known_tool_names=self.DOTTED_KNOWN)
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "audio")
        args = json.loads(out["function"]["arguments"])
        self.assertEqual(args["action"], "set_volume")
        self.assertEqual(args["level"], 20)

    def test_normal_form_still_works(self):
        out = detect_leaked_tool_call(
            'window(action="close", query="x")', known_tool_names=self.DOTTED_KNOWN)
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "window")

    def test_unknown_dotted_tool_rejected(self):
        out = detect_leaked_tool_call(
            "notatool.foo(x=1)", known_tool_names=self.DOTTED_KNOWN)
        self.assertIsNone(out)


class TestMultiCallLeak(unittest.TestCase):
    """Two space-separated leaked calls — `system(action='memory')
    system(action='recall')` — must rescue the FIRST. Live repro 2026-05-20:
    the greedy whole-string regex grabbed a broken body and gave up, so the
    reminder turn ran no tool."""

    K = {"system", "memory", "reminder", "web", "whatsapp"}

    def test_two_space_separated_calls_rescues_first(self):
        out = detect_leaked_tool_call(
            "system(action='memory') system(action='recall')",
            known_tool_names=self.K)
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "system")
        args = json.loads(out["function"]["arguments"])
        self.assertEqual(args.get("action"), "memory")

    def test_narration_then_two_calls(self):
        out = detect_leaked_tool_call(
            'Voy a hacer web(action="search") y luego whatsapp(action="send")',
            known_tool_names=self.K)
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "web")

    def test_prose_with_parens_not_a_call(self):
        out = detect_leaked_tool_call(
            "esto no es (un call) de verdad", known_tool_names=self.K)
        self.assertIsNone(out)


class TestCapitalizedToolName(unittest.TestCase):
    """Regresión 2026-05-30 (CATASTRÓFICA): el 4B capitalizó el nombre de la
    tool como si fuera nombre propio — `Web(action="search", query="mejor lego
    batman")` en vez de `web(...)`. Los regex del detector exigían `[a-z]` como
    primer char, así que NO matcheaban `Web`, el rescue fallaba, y el texto
    crudo `Web(action="search"...)` llegó LITERAL al usuario como respuesta.

    Fix: primer char [a-zA-Z] + normalizar el nombre a minúsculas antes del
    allowlist. Seguro: las 68 tools registradas son lowercase, sin colisiones
    al bajar a minúsculas. El allowlist sigue rechazando nombres que no son
    tools (`Banana(...)`), capitalizados o no.
    """

    K = {"web", "media", "browser", "whatsapp", "system", "window", "steam"}

    def test_capitalized_web_kwargs_rescued_as_lowercase(self):
        out = detect_leaked_tool_call(
            'Web(action="search", query="mejor lego batman")',
            known_tool_names=self.K)
        self.assertIsNotNone(out, "Web(...) capitalizado debe rescatarse")
        self.assertEqual(out["function"]["name"], "web")
        args = json.loads(out["function"]["arguments"])
        self.assertEqual(args["action"], "search")
        self.assertEqual(args["query"], "mejor lego batman")

    def test_lowercase_still_works(self):
        # Regresión inversa: el fix no debe romper el caso lowercase normal.
        out = detect_leaked_tool_call(
            'web(action="search", query="x")', known_tool_names=self.K)
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "web")

    def test_capitalized_dotted_method_rescued(self):
        out = detect_leaked_tool_call(
            'Window.close(query="das Fenster")', known_tool_names=self.K)
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "window")
        args = json.loads(out["function"]["arguments"])
        self.assertEqual(args.get("action"), "close")

    def test_capitalized_json_form_rescued(self):
        out = detect_leaked_tool_call(
            '{"name": "Steam", "arguments": {"action": "open"}}',
            known_tool_names=self.K)
        self.assertIsNotNone(out)
        self.assertEqual(out["function"]["name"], "steam")

    def test_capitalized_unknown_tool_still_rejected(self):
        # El allowlist debe seguir rechazando un nombre-capitalizado que NO es
        # tool — el fix no abre la puerta a leer prosa como call.
        out = detect_leaked_tool_call(
            'Banana(action="peel")', known_tool_names=self.K)
        self.assertIsNone(out)

    def test_capitalized_prose_not_a_call(self):
        out = detect_leaked_tool_call(
            "Esto(es algo) que dije.", known_tool_names=self.K)
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
