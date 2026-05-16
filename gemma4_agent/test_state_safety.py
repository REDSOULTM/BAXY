"""Tests de defense-in-depth: extractor + validator + sanitizer.

Bugs reales encontrados en sesion 11:43-11:47 (2026-05-16):
  1. "Hola" guardado como profile de hbo_max.
  2. "Quien eres" guardado como profile de disney.
  3. LLM emitio <|tool_call>...<tool_call|> como texto literal.

Estos tests previenen regresion de esos casos.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("GEMMA4_LLAMA_AUTO_START", "0")

from .agent import Gemma4Agent
from .domain_tools import (
    _INVALID_PROFILE_NAMES,
    _is_valid_profile_name,
    _set_streaming_preference,
    _get_streaming_preference,
)
from .reasoning import sanitize_text
from .state import AgentState


def _fresh_state() -> AgentState:
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    p = Path(tmp.name)
    p.unlink(missing_ok=True)
    return AgentState(path=p)


class TestExtractorRejectsGreetingsAndQuestions(unittest.TestCase):
    """REGRESSION: extractor permitia 'Hola' / 'Quien eres' como profile."""

    def test_hola_rejected(self):
        for v in ("Hola", "hola", "Holas", "HOLA", "  hola  "):
            self.assertIsNone(
                Gemma4Agent._extract_profile_name(v),
                f"{v!r} should NOT be a profile name",
            )

    def test_questions_rejected(self):
        for v in ("Quien eres", "Quién eres", "que tal", "Qué tal",
                  "Como estas", "Cómo estás", "Cual es", "Cuál es",
                  "Que sos", "Quien sos"):
            self.assertIsNone(
                Gemma4Agent._extract_profile_name(v),
                f"{v!r} should NOT be a profile name",
            )

    def test_thanks_and_confirmations_rejected(self):
        for v in ("Gracias", "thanks", "ok", "okay", "vale",
                  "si", "no", "bueno", "perfecto"):
            self.assertIsNone(
                Gemma4Agent._extract_profile_name(v),
                f"{v!r} should NOT be a profile name",
            )

    def test_pronouns_alone_rejected(self):
        for v in ("eres", "es", "Tú", "Tu", "soy"):
            self.assertIsNone(Gemma4Agent._extract_profile_name(v))

    def test_real_names_still_accepted(self):
        for v in ("Ema", "Emmanuel", "Bea", "Clara",
                  "REDSOULTM", "Mi perfil es Ema"):
            result = Gemma4Agent._extract_profile_name(v)
            self.assertIsNotNone(result, f"{v!r} should extract a name")


class TestStreamingPreferenceValidator(unittest.TestCase):
    """REGRESSION: _set_streaming_preference acepta nombres invalidos."""

    def test_validator_rejects_greetings(self):
        for v in ("Hola", "hola", "ok", "thanks", "X"):
            self.assertFalse(
                _is_valid_profile_name(v),
                f"{v!r} should be rejected as invalid profile name",
            )

    def test_validator_rejects_questions(self):
        for v in ("Quien eres", "Quien soy", "que tal"):
            self.assertFalse(_is_valid_profile_name(v))

    def test_validator_rejects_empty(self):
        for v in ("", "   ", "\t", "\n"):
            self.assertFalse(_is_valid_profile_name(v))

    def test_validator_rejects_no_letters(self):
        for v in ("!!", "123", "...", "*****"):
            self.assertFalse(_is_valid_profile_name(v))

    def test_validator_rejects_tool_call_leak(self):
        for v in ("<|tool_call|>", "tool_call: foo", "system: bar",
                  "user:Ema"):
            self.assertFalse(_is_valid_profile_name(v))

    def test_validator_accepts_real_names(self):
        for v in ("Ema", "Emmanuel", "Bea", "Clara",
                  "Em13", "Profile1"):
            self.assertTrue(_is_valid_profile_name(v))


class TestSetStreamingPreferenceDefense(unittest.TestCase):
    """REGRESSION: incluso si llaman _set_streaming_preference con basura,
    debe rechazarla en vez de corromper el state."""

    def test_set_with_invalid_name_rejected(self):
        state = _fresh_state()
        result = _set_streaming_preference(state, "netflix", "Hola")
        self.assertIsNotNone(result)
        self.assertFalse(result.get("ok", True))
        # Y NO debe haber escrito nada al state.
        self.assertIsNone(_get_streaming_preference(state, "netflix"))

    def test_set_with_question_as_name_rejected(self):
        state = _fresh_state()
        _set_streaming_preference(state, "disney", "Quien eres")
        self.assertIsNone(_get_streaming_preference(state, "disney"))

    def test_set_with_valid_name_works(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Emmanuel")
        self.assertEqual(_get_streaming_preference(state, "netflix"), "Emmanuel")

    def test_set_with_leading_trailing_whitespace_stripped(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "  Ema  ")
        self.assertEqual(_get_streaming_preference(state, "netflix"), "Ema")


class TestToolCallLeakSanitizer(unittest.TestCase):
    """REGRESSION: LLM a veces emite <|tool_call>...<tool_call|> como texto."""

    def test_strips_full_tool_call_leak(self):
        # Caso exacto del log 11:43:
        leak = (
            '<|tool_call>call:browser{action:<|"|>search<|"|>, '
            'browser:<|"|>google<|"|>, engine:<|"|>google<|"|>, '
            'query:<|"|>House of Dragon<|"|>}<tool_call|>'
        )
        self.assertEqual(sanitize_text(leak), "")

    def test_strips_partial_leak_keeps_real_content(self):
        mixed = "Listo, busque eso.\n<|tool_call>call:foo{}<tool_call|>"
        self.assertEqual(sanitize_text(mixed), "Listo, busque eso.")

    def test_strips_orphan_close_tag(self):
        self.assertEqual(sanitize_text("ok</tool_call|>"), "ok")
        self.assertEqual(sanitize_text("ok<tool_call|>"), "ok")

    def test_strips_orphan_open_tag(self):
        self.assertEqual(sanitize_text("ok<|tool_call|>"), "ok")

    def test_normal_text_unchanged(self):
        self.assertEqual(
            sanitize_text("Listo, abri Netflix."),
            "Listo, abri Netflix.",
        )

    def test_brackets_with_pipe_in_normal_text_not_stripped(self):
        # No queremos sobre-strippear. "[X|Y]" no es un tool_call.
        normal = "Opciones: [A|B|C]"
        self.assertEqual(sanitize_text(normal), normal)


if __name__ == "__main__":
    unittest.main()
