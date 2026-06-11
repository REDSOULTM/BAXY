"""Señales fuertes de idioma en FRASES CORTAS (it/pt/de) — 2026-06-11.

py3langid es poco fiable bajo ~3 palabras (medido: "chi sei?"→de hacía que la
identidad italiana saliera en ALEMÁN; "quem é você?"→fr daba "Je suis Baxy" al
gate pt). Señales estructurales exclusivas del idioma (ortografía y cerradas
funcionales), no keywords de contenido.
"""
import unittest

from gemma4_agent.agent_core.latency_helpers import detect_lang_strong_signal


class TestItalianShort(unittest.TestCase):
    def test_chi_inicial(self):
        self.assertEqual(detect_lang_strong_signal("chi sei?"), "it")
        self.assertEqual(detect_lang_strong_signal("chi è il tuo creatore?"), "it")

    def test_e_suelta_y_elisiones(self):
        self.assertEqual(detect_lang_strong_signal("è tardi"), "it")
        self.assertEqual(detect_lang_strong_signal("cos'è questo?"), "it")
        self.assertEqual(detect_lang_strong_signal("c'è qualcosa?"), "it")

    def test_perche(self):
        self.assertEqual(detect_lang_strong_signal("perché?"), "it")

    def test_tai_chi_no_es_italiano(self):
        # "chi" solo cuenta al INICIO: "what is tai chi" debe quedar para
        # py3langid (en), no caer a it.
        self.assertIsNone(detect_lang_strong_signal("what is tai chi"))

    def test_cest_frances_no_cae_a_it(self):
        self.assertIsNone(detect_lang_strong_signal("c'est quoi ça ?"))


class TestPortugueseShort(unittest.TestCase):
    def test_quem_voce(self):
        self.assertEqual(detect_lang_strong_signal("quem é você?"), "pt")
        self.assertEqual(detect_lang_strong_signal("você pode me ajudar"), "pt")

    def test_voce_acentuado_no_choca_con_it_voce(self):
        # it "voce" (voz) sin acento NO debe dar pt
        self.assertIsNone(detect_lang_strong_signal("ho sentito una voce"))


class TestGermanShort(unittest.TestCase):
    def test_eszett(self):
        self.assertEqual(detect_lang_strong_signal("weiß nicht"), "de")
        self.assertEqual(detect_lang_strong_signal("schließe das Fenster bitte"), "de")


class TestPrecedencia(unittest.TestCase):
    def test_es_pt_intactos(self):
        self.assertEqual(detect_lang_strong_signal("qué hora es"), "es")
        self.assertEqual(detect_lang_strong_signal("não funciona"), "pt")
        self.assertEqual(detect_lang_strong_signal("¿puedes ayudarme?"), "es")


if __name__ == "__main__":
    unittest.main()
