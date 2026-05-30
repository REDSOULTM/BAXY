"""Trigger-inject de skills (2026-05-29): el 4B no emite skill_load (0/5 medido),
así que inyectamos la receta de la skill que matchea semánticamente el pedido.
Tests con embed REAL (valida el match calibrado: matches >0.5, control <0.21) +
fallbacks. Gate GEMMA4_SKILLS_AUTOINJECT."""
import os
import unittest

from ..tools_pkg.skills_registry import (
    autoinject_skill, scan_skills, reset_autoinject_cache,
)
from ..agent_core.agent import _skills_autoinject_enabled


class TestAutoinjectSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ..routing.semantic_router import embed
        cls.embed = staticmethod(embed)
        cls.skills = scan_skills()
        reset_autoinject_cache()

    def test_matches_strong_skill(self):
        # "app crashea, diagnosticá" matchea debug-app-crash (calibrado sim=0.733)
        name, body = autoinject_skill(
            "una app me crashea, diagnosticá por qué", self.skills, embed_fn=self.embed)
        self.assertEqual(name, "debug-app-crash")
        self.assertGreater(len(body), 50)

    def test_matches_research(self):
        name, _ = autoinject_skill(
            "investigá sobre este tema en internet y resumime",
            self.skills, embed_fn=self.embed)
        self.assertEqual(name, "research-and-summarize")

    def test_control_no_match(self):
        # charla / acción simple NO debe activar skill (sim < umbral)
        for txt in ("qué hora es", "subí el volumen", "hola cómo estás"):
            name, _ = autoinject_skill(txt, self.skills, embed_fn=self.embed)
            self.assertIsNone(name, f"falso positivo en {txt!r}")

    def test_hard_negative_suppression(self):
        """R3.2 (2026-05-30, arXiv:2510.22670): los `limitations` en prosa
        SUPRIMEN skills cuando la query matchea más "lo que la skill NO hace".
        Estos comparten un sustantivo con una skill pero el verbo indica otra
        intención (la cubre una TOOL del router, no una skill multi-paso).
        MEDIDO: sin supresión estos disparaban FP; con `limitations` → None."""
        hard_negatives = [
            "subí el brillo de la pantalla",        # vs screenshot (pantalla)
            "desmuteá mi micrófono en discord",     # vs voice-record (micrófono)
            "poné en pantalla completa el video",   # vs screenshot/download (video)
            "extraé el texto de un pdf",            # vs download (pdf)
            "resumime todo lo anterior",            # vs research (resumir)
        ]
        for txt in hard_negatives:
            name, _ = autoinject_skill(txt, self.skills, embed_fn=self.embed)
            self.assertIsNone(
                name, f"hard-negative no suprimido (FP) en {txt!r} -> {name}")

    def test_no_embed_is_safe(self):
        name, body = autoinject_skill("una app me crashea", self.skills, embed_fn=None)
        self.assertIsNone(name)
        self.assertEqual(body, "")

    def test_short_text_skipped(self):
        name, _ = autoinject_skill("hi", self.skills, embed_fn=self.embed)
        self.assertIsNone(name)

    def test_embed_exception_is_safe(self):
        def _boom(_):
            raise RuntimeError("encoder down")
        name, body = autoinject_skill("una app me crashea", self.skills, embed_fn=_boom)
        self.assertIsNone(name)
        self.assertEqual(body, "")


class TestGate(unittest.TestCase):
    def test_default_on(self):
        # 2026-05-29: default-ON (validado live: 4B sigue la receta, 0 FP; perf OK
        # ~2-4ms mediana < 5ms). Kill-switch GEMMA4_SKILLS_AUTOINJECT=0 sigue activo.
        prev = os.environ.pop("GEMMA4_SKILLS_AUTOINJECT", None)
        try:
            self.assertTrue(_skills_autoinject_enabled())  # default ON
            os.environ["GEMMA4_SKILLS_AUTOINJECT"] = "0"
            self.assertFalse(_skills_autoinject_enabled())  # kill-switch
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_SKILLS_AUTOINJECT", None)
            else:
                os.environ["GEMMA4_SKILLS_AUTOINJECT"] = prev


if __name__ == "__main__":
    unittest.main()
