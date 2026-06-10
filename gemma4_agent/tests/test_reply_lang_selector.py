"""Selector de idioma del usuario (2026-06-07).

El user pidió un selector en settings para FIJAR el idioma. _reply_lang respeta
GEMMA4_VOICE_LANG: si está fijo (es/en/pt/fr/de/it) usa ESE sin auto-detectar
(elimina el drift a otro idioma en la respuesta); si vacío/auto -> _detect_lang
(comportamiento Automático actual). NO modifica _detect_lang.
"""
from __future__ import annotations

import os
import types
import unittest

from gemma4_agent.agent_core.agent import (
    Gemma4Agent,
    _detect_lang,
    _reply_lang,
    _reply_language_mismatch,
    _turn_language_instruction,
)


class ReplyLangSelectorTest(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("GEMMA4_VOICE_LANG")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("GEMMA4_VOICE_LANG", None)
        else:
            os.environ["GEMMA4_VOICE_LANG"] = self._prev

    def test_fixed_lang_overrides_text(self):
        # idioma fijo -> ese idioma SIEMPRE, aunque el texto sea de otro idioma
        # (clava la respuesta; elimina el drift a francés/inglés del bug).
        os.environ["GEMMA4_VOICE_LANG"] = "es"
        self.assertEqual(_reply_lang("hello there my friend"), "es")
        self.assertEqual(_reply_lang("bonjour le monde comment ça va"), "es")

    def test_fixed_lang_normalizes_region(self):
        os.environ["GEMMA4_VOICE_LANG"] = "en-US"
        self.assertEqual(_reply_lang("hola amigo cómo estás"), "en")
        os.environ["GEMMA4_VOICE_LANG"] = "PT_BR"
        self.assertEqual(_reply_lang("hello world"), "pt")

    def test_empty_is_auto_detect(self):
        # vacío = Automático. Un idioma CLARO se respeta (no se ancla al SO).
        # 2026-06-10 (mission-eval): el modo auto vuelve a CONFIAR en _detect_lang
        # (robusto: py3langid + verbos + quita nombres propios). Anclar al SO sobre
        # una detección clara rompía a TODOS los usuarios no-español ("tell me the
        # time"/"druck mir das PDF" -> respuesta en ES). _detect_lang ya protege el
        # drift por nombre propio ("háblame de Mortal Kombat" -> es).
        os.environ["GEMMA4_VOICE_LANG"] = ""
        # un comando inglés CLARO (verbo imperativo 'open') -> en, pese al SO.
        self.assertEqual(_reply_lang("open Chrome please"), "en")
        # un pedido inglés claro ("tell me the time") -> en (antes drifteaba a es).
        self.assertEqual(_reply_lang("tell me the time"), "en")
        # texto sin idioma reconocible -> el reply NUNCA queda sin idioma válido.
        self.assertIn(_reply_lang("xyzzy plugh foo bar"),
                      {"es", "en", "pt", "fr", "de", "it"})

    def test_unset_anchors_to_os_or_detect(self):
        # un idioma CLARO se respeta aunque el SO sea otro (señal fuerte: verbo fr).
        os.environ.pop("GEMMA4_VOICE_LANG", None)
        self.assertEqual(_reply_lang("ouvre Spotify maintenant"), "fr")

    def test_invalid_value_falls_back_to_auto(self):
        # un código no soportado -> modo auto (ancla SO / detección), no rompe.
        os.environ["GEMMA4_VOICE_LANG"] = "xx"
        self.assertEqual(_reply_lang("open Chrome please"), "en")  # señal fuerte EN

    def test_turn_prompt_carries_selected_reply_language(self):
        os.environ["GEMMA4_VOICE_LANG"] = "es"
        hint = _turn_language_instruction("Quien eres")
        self.assertIn("Selected conversation language: Spanish (es)", hint)
        self.assertIn("Reply ONLY in Spanish", hint)
        self.assertIn("prior assistant replies", hint)

    def test_reply_language_mismatch_detects_english_reply_to_spanish_turn(self):
        os.environ["GEMMA4_VOICE_LANG"] = "es"
        needs, target, reply_lang = _reply_language_mismatch(
            "Quien eres",
            "I am Baxy, your local Windows voice assistant powered by Gemma 4.",
        )
        self.assertTrue(needs)
        self.assertEqual(target, "es")
        self.assertEqual(reply_lang, "en")

    def test_reply_language_repair_uses_llm_rewrite(self):
        os.environ["GEMMA4_VOICE_LANG"] = "es"

        class _Trace:
            def __init__(self):
                self.events = []

            def event(self, *args, **kwargs):
                self.events.append((args, kwargs))

        class _Client:
            def __init__(self):
                self.calls = []

            def chat(self, messages, **kwargs):
                self.calls.append((messages, kwargs))
                return {"choices": [{"message": {
                    "content": "Soy Baxy, tu asistente local de voz para Windows."
                }}]}

        class _Self:
            pass

        fake = _Self()
        fake.client = _Client()
        fake.trace = _Trace()
        fake._router_model_for = lambda messages: None
        fake._tts_streamed = True
        fake._tts_streamed_text = "I am Baxy"
        fake._tts_info_stream = True
        fake._llm_rewrite_reply_language = types.MethodType(
            Gemma4Agent._llm_rewrite_reply_language, fake)

        fixed, repaired = Gemma4Agent._repair_reply_language_if_needed(
            fake,
            "Quien eres",
            "I am Baxy, your local Windows voice assistant powered by Gemma 4.",
            "turn-test",
        )
        self.assertTrue(repaired)
        self.assertEqual(_detect_lang(fixed), "es")
        self.assertEqual(len(fake.client.calls), 1)
        self.assertFalse(fake._tts_streamed)


if __name__ == "__main__":
    unittest.main()
