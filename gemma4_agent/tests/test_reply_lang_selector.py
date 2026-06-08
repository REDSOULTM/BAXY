"""Selector de idioma del usuario (2026-06-07).

El user pidió un selector en settings para FIJAR el idioma. _reply_lang respeta
GEMMA4_VOICE_LANG: si está fijo (es/en/pt/fr/de/it) usa ESE sin auto-detectar
(elimina el drift a otro idioma en la respuesta); si vacío/auto -> _detect_lang
(comportamiento Automático actual). NO modifica _detect_lang.
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.agent_core.agent import _reply_lang, _detect_lang


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
        # vacío = Automático -> delega en _detect_lang (sin tocarlo).
        os.environ["GEMMA4_VOICE_LANG"] = ""
        self.assertEqual(_reply_lang("hello there my friend"),
                         _detect_lang("hello there my friend"))

    def test_unset_is_auto_detect(self):
        os.environ.pop("GEMMA4_VOICE_LANG", None)
        txt = "bonjour le monde comment ça va aujourd'hui"
        self.assertEqual(_reply_lang(txt), _detect_lang(txt))

    def test_invalid_value_falls_back_to_auto(self):
        # un código no soportado -> auto (no rompe).
        os.environ["GEMMA4_VOICE_LANG"] = "xx"
        txt = "hello there my friend"
        self.assertEqual(_reply_lang(txt), _detect_lang(txt))


if __name__ == "__main__":
    unittest.main()
