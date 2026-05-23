"""Per-language STT profiles: el initial_prompt y el whisper_language deben
derivar del perfil de idioma, no estar hardcodeados a español.

Pedido del user 2026-05-22: un usuario en inglés/otro idioma NO debe quedar con
config española. Config por idioma + default es (Spanglish).
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from gemma4_agent.voice.inventory import build_initial_prompt
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
        import os
        with patch.dict("os.environ", {"GEMMA4_VOICE_LANG": "en"}):
            self.assertEqual(lp.resolve_lang(), "en")


class PerLanguagePromptTest(unittest.TestCase):
    def test_spanish_prompt_is_spanish_with_bilingual_seed(self):
        p = build_initial_prompt(lang="es")
        self.assertIn("español", p)
        self.assertIn("abre Chrome", p)
        self.assertIn("open Chrome", p)  # seed bilingüe anti-anglicismo

    def test_english_prompt_is_english_not_spanish(self):
        p = build_initial_prompt(lang="en")
        self.assertIn("English", p)
        self.assertIn("open Chrome", p)
        self.assertNotIn("español", p)
        self.assertNotIn("Conversación", p)

    def test_portuguese_prompt_is_portuguese(self):
        p = build_initial_prompt(lang="pt")
        self.assertIn("português", p)
        self.assertNotIn("español", p)

    def test_all_profiles_under_cap(self):
        for code in lp.PROFILES:
            p = build_initial_prompt(lang=code)
            self.assertLessEqual(len(p), lp.PROMPT_CHAR_CAP)

    def test_proper_nouns_present_in_every_language(self):
        # Apps son agnósticas del idioma -> deben aparecer en todos.
        for code in lp.PROFILES:
            p = build_initial_prompt(lang=code)
            self.assertIn("Spotify", p, f"Spotify missing in {code} prompt")

    def test_whisper_language_matches_profile(self):
        self.assertEqual(lp.get_profile("es").whisper_language, "es")
        self.assertEqual(lp.get_profile("en").whisper_language, "en")
        self.assertEqual(lp.get_profile("pt").whisper_language, "pt")


if __name__ == "__main__":
    unittest.main()
