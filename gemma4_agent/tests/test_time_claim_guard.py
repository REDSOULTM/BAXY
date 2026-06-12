"""Guard de hora fabricada (bug en vivo 2026-06-10: media→attempted respondió
"Es las 10:42 de la mañana." a las 21:56). Detector estructural en
reply_validator + repair inline en agent_guards.
"""
from __future__ import annotations

import unittest

from gemma4_agent.safety_pkg.reply_validator import (
    clock_time_claim_unfounded,
    strip_unfounded_time_sentences,
)
from gemma4_agent.agent_core.agent_guards import repair_unfounded_time_claim_inline


def _ev(name: str, result: dict, args: dict | None = None) -> dict:
    return {"name": name, "args": args or {}, "result": result}


class ClockTimeClaimTest(unittest.TestCase):
    # --- el bug real, verbatim ---
    def test_live_bug_media_attempted_fires(self) -> None:
        events = [_ev("media", {"ok": True, "status": "attempted",
                                "query": "Bohemian Rhapsody"})]
        self.assertTrue(clock_time_claim_unfounded(
            "pon una canción de Michael Jackson",
            "Es las 10:42 de la mañana.", events))

    def test_no_tool_turn_fabricated_time_fires(self) -> None:
        self.assertTrue(clock_time_claim_unfounded(
            "ton an", "La hora actual es 1:29 de la madrugada.", []))

    # --- casos legítimos que NO deben disparar ---
    def test_time_grounded_by_system_tool_passes(self) -> None:
        events = [_ev("system", {"ok": True, "time": "21:56:03",
                                 "date": "2026-06-10"})]
        self.assertFalse(clock_time_claim_unfounded(
            "qué hora es", "Son las 21:56.", events))

    def test_12h_reply_grounded_by_24h_result_passes(self) -> None:
        events = [_ev("system", {"ok": True, "time": "21:56:03"})]
        self.assertFalse(clock_time_claim_unfounded(
            "what time is it", "It's 9:56 PM.", events))

    def test_time_echoed_from_user_passes(self) -> None:
        # "recordame a las 7:30" -> "Listo, te aviso a las 7:30." (eco honesto)
        self.assertFalse(clock_time_claim_unfounded(
            "recordame a las 7:30 tomar agua",
            "Listo, te aviso a las 7:30.",
            [_ev("notifications", {"ok": True})]))

    def test_alarm_iso_result_grounds_zero_padded_time(self) -> None:
        events = [_ev("notifications", {"ok": True, "when": "2026-06-11T07:00:00"})]
        self.assertFalse(clock_time_claim_unfounded(
            "poné una alarma a las 7 de la mañana",
            "Listo, alarma a las 07:00.", events))

    def test_duration_without_time_marker_passes(self) -> None:
        # duración de video sin marcador de hora-del-día -> fuera de alcance
        self.assertFalse(clock_time_claim_unfounded(
            "cuánto dura el video", "El video dura 3:45.", []))

    def test_plain_confirmation_passes(self) -> None:
        self.assertFalse(clock_time_claim_unfounded(
            "abre Spotify", "Listo, abrí Spotify.",
            [_ev("app", {"ok": True})]))

    # --- strip de último recurso ---
    def test_strip_removes_only_time_sentences(self) -> None:
        out = strip_unfounded_time_sentences(
            "Abrí Spotify. Es las 10:42 de la mañana.")
        self.assertEqual(out, "Abrí Spotify.")

    def test_strip_all_time_returns_empty(self) -> None:
        self.assertEqual(
            strip_unfounded_time_sentences("Es las 10:42 de la mañana."), "")


class RepairInlineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.events = [_ev("media", {"ok": True, "status": "attempted"})]
        self.bad = "Es las 10:42 de la mañana."

    def test_regen_action_replaces_reply(self) -> None:
        fixed = repair_unfounded_time_claim_inline(
            self.bad, "pon una canción de Michael Jackson", self.events, "t1",
            regen_action=lambda: "Abrí Spotify con la búsqueda; falta darle play.",
            regen_knowledge=lambda: "no debería usarse",
        )
        self.assertEqual(fixed, "Abrí Spotify con la búsqueda; falta darle play.")

    def test_regen_still_bad_falls_back_to_strip(self) -> None:
        fixed = repair_unfounded_time_claim_inline(
            self.bad, "pon una canción", self.events, "t1",
            regen_action=lambda: "Son las 11:11 de la noche.",
            regen_knowledge=None,
        )
        # strip deja vacío -> fallback "Listo." en turnos con tools
        self.assertEqual(fixed, "Listo.")

    def test_no_events_uses_knowledge_regen(self) -> None:
        fixed = repair_unfounded_time_claim_inline(
            "Son las 4:20 de la tarde.", "ton an", [], "t1",
            regen_action=lambda: "no debería usarse",
            regen_knowledge=lambda: "No te entendí, ¿me lo repetís?",
        )
        self.assertEqual(fixed, "No te entendí, ¿me lo repetís?")

    def test_grounded_reply_untouched(self) -> None:
        events = [_ev("system", {"ok": True, "time": "21:56:03"})]
        good = "Son las 21:56."
        fixed = repair_unfounded_time_claim_inline(
            good, "qué hora es", events, "t1",
            regen_action=lambda: "otro", regen_knowledge=lambda: "otro",
        )
        self.assertEqual(fixed, good)

    def test_env_gate_off_leaves_reply(self) -> None:
        import os
        os.environ["GEMMA4_TIME_CLAIM_GUARD"] = "0"
        try:
            fixed = repair_unfounded_time_claim_inline(
                self.bad, "pon una canción", self.events, "t1",
                regen_action=lambda: "x", regen_knowledge=lambda: "x",
            )
            self.assertEqual(fixed, self.bad)
        finally:
            os.environ.pop("GEMMA4_TIME_CLAIM_GUARD", None)


class WordedClockTimeClaimTest(unittest.TestCase):
    """Hora DELETREADA (bug en vivo 2026-06-12: media→dispatched respondió
    "Es las dos de la madrugada." a las 01:49 — ni pedida ni correcta; el
    detector de dígitos no la veía)."""

    # --- el bug real, verbatim ---
    def test_live_bug_worded_time_after_media_fires(self) -> None:
        events = [_ev("media", {"ok": True, "status": "dispatched",
                                "query": "pon una canción"})]
        self.assertTrue(clock_time_claim_unfounded(
            "Pon una canción en Spotify",
            "Es las dos de la madrugada.", events))

    def test_worded_time_no_tool_fires(self) -> None:
        self.assertTrue(clock_time_claim_unfounded(
            "hola", "Son las tres de la tarde.", []))

    def test_worded_time_multilang_fires(self) -> None:
        for reply in ("It's two in the morning.",
                      "Il est deux heures.",
                      "Es ist zwei Uhr.",
                      "São duas da madrugada.",
                      "Sono le due di notte."):
            self.assertTrue(
                clock_time_claim_unfounded("play a song", reply, []),
                msg=reply)

    # --- sustento legítimo ---
    def test_worded_time_grounded_by_system_tool_passes(self) -> None:
        events = [_ev("system", {"ok": True, "time": "02:04:11"})]
        self.assertFalse(clock_time_claim_unfounded(
            "qué hora es", "Son las dos de la madrugada.", events))

    def test_worded_time_grounded_pm_mod12_passes(self) -> None:
        events = [_ev("system", {"ok": True, "time": "14:30:00"})]
        self.assertFalse(clock_time_claim_unfounded(
            "qué hora es", "Son las dos y media de la tarde.", events))

    def test_worded_time_echoed_from_user_passes(self) -> None:
        self.assertFalse(clock_time_claim_unfounded(
            "recordame que es las dos de la tarde la reunión",
            "Listo, la reunión es las dos de la tarde.",
            [_ev("notifications", {"ok": True})]))

    # --- falsos positivos que NO deben disparar ---
    def test_idiom_dos_caras_passes(self) -> None:
        self.assertFalse(clock_time_claim_unfounded(
            "qué opinás", "Son las dos caras de la misma moneda.", []))

    def test_counting_things_passes(self) -> None:
        self.assertFalse(clock_time_claim_unfounded(
            "cuántas ventanas hay", "Veo dos ventanas abiertas.", []))

    # --- strip de oraciones deletreadas ---
    def test_strip_removes_worded_time_sentence(self) -> None:
        out = strip_unfounded_time_sentences(
            "Listo, puse la música. Es las dos de la madrugada.")
        self.assertEqual(out, "Listo, puse la música.")


if __name__ == "__main__":
    unittest.main()
