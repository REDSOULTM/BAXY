"""Tests de defense-in-depth: validator + sanitizer.

2026-05-16: borrado el extractor _extract_profile_name + el pending
action store. Confiamos en el LLM para mantener el contexto cross-turn:
  - media retorna needs_user/streaming_profile.
  - LLM pregunta al user "¿cuál es tu perfil?".
  - User responde "Ema" (o "mi perfil es Ema", o lo que sea).
  - LLM ve el history (su pregunta previa + respuesta) y llama media
    de nuevo con profile='Ema'.

El validator queda como DEFENSE IN DEPTH: si el LLM por alguna razon
pasa profile="Hola" o profile="<|tool_call|>", el state NO se corrompe.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("GEMMA4_LLAMA_AUTO_START", "0")

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
