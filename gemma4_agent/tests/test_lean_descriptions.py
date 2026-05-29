"""Tests para las descripciones de schema LEAN (opt-in GEMMA4_LEAN_RULES, dormant).

MOCKS (sin modelo/GPU):
  - existen lean descs para los tools pesados y son MAS CHICAS
  - preservan el contenido CRITICO PARA SELECCION (qué hace + límites NO-usar-para)
  - _with_lean_description NO muta el literal global (contract-test sigue a salvo)
  - gating del flag

La CALIDAD real (que el modelo siga seleccionando bien el tool con la desc lean) NO
se cubre aca — las descripciones DRIVEN la selección, es el trim de MAYOR riesgo →
validación EN VIVO. Ver PLAN_optimizacion_prompt_tokens.md.
"""
import os
import unittest

from ..tools_pkg import tools as T

HEAVY = ["whatsapp", "computer_use", "media", "audio"]
CRITICAL = {
    "whatsapp": ["send_message", "SLOT FILLING", "auto_send", "contact", "no tengo"],
    "computer_use": ["goal", "Discord", "NOT for", "whatsapp"],
    "media": ["provider", "spotify", "streaming_profile", "auto_play"],
    "audio": ["set_volume", "media_stop", "NOT to close"],
}


class _LeanEnv:
    def __init__(self, on: bool):
        self.on = on
        self.prev = None

    def __enter__(self):
        self.prev = os.environ.get("GEMMA4_LEAN_RULES")
        if self.on:
            os.environ["GEMMA4_LEAN_RULES"] = "1"
        else:
            os.environ["GEMMA4_LEAN_RULES"] = "0"  # v22: default es ON, off explícito
        return self

    def __exit__(self, *exc):
        if self.prev is None:
            os.environ.pop("GEMMA4_LEAN_RULES", None)
        else:
            os.environ["GEMMA4_LEAN_RULES"] = self.prev


class TestLeanDescriptions(unittest.TestCase):
    def _orig(self, name):
        for s in T.COMPOUND_TOOL_SCHEMAS:
            if s.get("function", {}).get("name") == name:
                return s
        raise KeyError(name)

    def test_lean_dict_covers_heavy(self):
        for n in HEAVY:
            self.assertIn(n, T.LEAN_DESCRIPTIONS)

    def test_lean_smaller_than_original(self):
        for n in HEAVY:
            orig = self._orig(n)["function"]["description"]
            self.assertLess(len(T.LEAN_DESCRIPTIONS[n]), len(orig), f"{n}: lean not smaller")

    def test_lean_preserves_selection_critical(self):
        for n, toks in CRITICAL.items():
            lean = T.LEAN_DESCRIPTIONS[n]
            for t in toks:
                self.assertIn(t, lean, f"{n} lean DROPPED selection-critical token: {t!r}")

    def test_with_lean_does_not_mutate_global(self):
        orig = self._orig("whatsapp")
        before = orig["function"]["description"]
        swapped = T._with_lean_description(orig)
        self.assertEqual(swapped["function"]["description"], T.LEAN_DESCRIPTIONS["whatsapp"])
        self.assertEqual(orig["function"]["description"], before, "GLOBAL literal was mutated!")

    def test_non_heavy_passthrough_same_object(self):
        fs = self._orig("filesystem")
        self.assertIs(T._with_lean_description(fs), fs)

    def test_flag_gating(self):
        with _LeanEnv(False):
            self.assertFalse(T._lean_descriptions_on())
        with _LeanEnv(True):
            self.assertTrue(T._lean_descriptions_on())


if __name__ == "__main__":
    unittest.main()
