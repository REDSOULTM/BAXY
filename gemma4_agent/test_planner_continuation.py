"""Tests for planner continuation hint (last_assistant_text).

Bug observado en sesion 12:22 (2026-05-16):
  Turn N: agent pregunta "¿Cuál es tu perfil en Disney+?"
  Turn N+1: user responde "Ema" -> SUBSET=[] (vacio) porque "Ema" no
    matchea ningun keyword.
  -> LLM no ve media en el subset, no puede llamar media, dice algo
    irrelevante.

Fix: el planner ahora acepta last_assistant_text. Si menciona "perfil"
+ una plataforma de streaming, fuerza media en el subset para el
turn siguiente (asumiendo que el user esta respondiendo al perfil).
"""
from __future__ import annotations

import unittest

from .planner import plan_mission, select_tool_names


class TestContinuationHintForStreaming(unittest.TestCase):

    def test_short_reply_after_profile_question_keeps_media(self):
        prev = "¿Cuál es tu perfil en Disney+? Lo guardo y la próxima vez no te pregunto."
        for reply in ("Ema", "Emmanuel", "Clara", "soy Em"):
            plan = plan_mission(reply)
            subset = select_tool_names(reply, plan, last_assistant_text=prev)
            self.assertIn("media", subset,
                          f"reply={reply!r} should keep media in subset")

    def test_without_hint_short_reply_subset_empty(self):
        # Sin el hint, "Ema" no produce ningun subset — eso fue el bug.
        plan = plan_mission("Ema")
        subset = select_tool_names("Ema", plan)
        self.assertEqual(subset, [])

    def test_hint_works_for_all_streaming_platforms(self):
        cases = [
            "¿Cuál es tu perfil en Netflix?",
            "Cual es tu perfil de Disney?",
            "¿Tu perfil de Disney+?",
            "What is your profile on HBO Max?",
            "Tu profile en Amazon Prime?",
            "¿Tu perfil en Spotify?",
        ]
        for prev in cases:
            plan = plan_mission("Emma")
            subset = select_tool_names("Emma", plan, last_assistant_text=prev)
            self.assertIn("media", subset, f"prev={prev!r}")

    def test_hint_does_not_apply_for_non_streaming_question(self):
        # Si el assistant pregunto algo sin streaming context, no forzar media.
        prev = "¿A quién le mando el mensaje?"  # context: whatsapp
        plan = plan_mission("Ema")
        subset = select_tool_names("Ema", plan, last_assistant_text=prev)
        # subset puede ser [] o algo que NO sea media.
        self.assertNotIn("media", subset)

    def test_hint_does_not_override_strong_user_intent(self):
        # Si el user dice algo claramente distinto (verbo de comando), el
        # planner lo respeta. Media puede aparecer aun como precaucion,
        # pero el subset NO sera solo media.
        prev = "¿Cuál es tu perfil en Netflix?"
        plan = plan_mission("borra el archivo test.txt")
        subset = select_tool_names("borra el archivo test.txt", plan,
                                    last_assistant_text=prev)
        # Filesystem debe estar (es el match real del comando)
        self.assertIn("filesystem", subset)

    def test_no_hint_passed_works_as_before(self):
        # El parametro es opcional.
        plan = plan_mission("abre Steam")
        subset = select_tool_names("abre Steam", plan)
        self.assertIn("steam", subset)


if __name__ == "__main__":
    unittest.main()
