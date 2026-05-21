"""sanitize_text must strip thinking even when the <think> tag is UNCLOSED
(generation cut mid-thinking by the token budget/timeout) and remove stray
model control tokens (<|end|> etc). Otherwise raw model-internal markup LEAKS to
the user — a visible UX failure, more likely now that turns have token budgets."""
from __future__ import annotations

import unittest

from gemma4_agent.reasoning import sanitize_text


class TestSanitizeUnclosedThink(unittest.TestCase):
    def test_closed_think_still_works(self):
        self.assertEqual(sanitize_text("<think>razono</think>Hola"), "Hola")

    def test_unclosed_think_is_stripped(self):
        # Budget cut the generation mid-thinking, no </think>.
        self.assertEqual(sanitize_text("<think>razonando y se cortó"), "")

    def test_reply_before_unclosed_think_kept(self):
        self.assertEqual(
            sanitize_text("Listo, abrí Spotify <think>ahora pienso"),
            "Listo, abrí Spotify",
        )

    def test_multiline_unclosed_think(self):
        self.assertEqual(sanitize_text("<think>\npaso 1\npaso 2\n"), "")

    def test_bare_control_token_stripped(self):
        self.assertEqual(sanitize_text("respuesta<|end|>"), "respuesta")

    def test_pipe_think_with_end_token(self):
        self.assertEqual(sanitize_text("<|think|>pienso<|end|>respuesta"), "respuesta")

    def test_plain_reply_unchanged(self):
        self.assertEqual(sanitize_text("Hola, ¿en qué ayudo?"), "Hola, ¿en qué ayudo?")

    def test_code_braces_not_touched(self):
        # The control-token regex must not eat normal text with pipes/braces.
        self.assertEqual(sanitize_text('El JSON es {"a": 1}'), 'El JSON es {"a": 1}')

    def test_none_and_nonstr(self):
        self.assertEqual(sanitize_text(None), "")
        self.assertEqual(sanitize_text(123), "123")


if __name__ == "__main__":
    unittest.main()
