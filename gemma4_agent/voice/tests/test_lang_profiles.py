"""Perfil de idioma del usuario (Parakeet-only 2026-06-17).

El perfil ya NO configura a Whisper (eliminado): es solo la identidad de idioma
del usuario (code/label) que la voz pasa como hint al agente. Se resuelve desde
GEMMA4_VOICE_LANG o el default 'es'.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from gemma4_agent.voice import lang_profiles as lp


class ResolveLangTest(unittest.TestCase):
    def test_default_is_spanish(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("GEMMA4_VOICE_LANG", None)
            self.assertEqual(lp.resolve_lang(), "es")

    def test_explicit_overrides_env(self):
        self.assertEqual(lp.resolve_lang("en"), "en")
        self.assertEqual(lp.resolve_lang("pt"), "pt")

    def test_accepts_locale_variants(self):
        self.assertEqual(lp.resolve_lang("es-419"), "es")
        self.assertEqual(lp.resolve_lang("en-US"), "en")
        self.assertEqual(lp.resolve_lang("pt_BR"), "pt")

    def test_unknown_falls_back_to_default(self):
        self.assertEqual(lp.resolve_lang("xx"), "es")
        self.assertEqual(lp.resolve_lang(""), "es")

    def test_env_var_used_when_no_explicit(self):
        with patch.dict("os.environ", {"GEMMA4_VOICE_LANG": "en"}):
            self.assertEqual(lp.resolve_lang(), "en")


class ProfileShapeTest(unittest.TestCase):
    def test_profile_exposes_code_and_label(self):
        p = lp.get_profile("es")
        self.assertEqual(p.code, "es")
        self.assertTrue(p.label)

    def test_no_whisper_legacy_fields(self):
        # El legado de Whisper (whisper_language, frame) se eliminó.
        p = lp.get_profile("en")
        self.assertFalse(hasattr(p, "whisper_language"))
        self.assertFalse(hasattr(p, "frame"))

    def test_get_profile_resolves_variants(self):
        self.assertEqual(lp.get_profile("pt-BR").code, "pt")
        self.assertEqual(lp.get_profile("xx").code, "es")  # fallback


if __name__ == "__main__":
    unittest.main()
