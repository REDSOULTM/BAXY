"""Unit tests for mission_goal + mission_outcome (TIER 2 #5)."""
from __future__ import annotations

import os
import unittest

from .mission_goal import (
    MissionGoal,
    OutcomeStatus,
    _detect_outcomes_in_clause,
    _kinds_for_call,
    _split_clauses,
)
from .mission_outcome import (
    _ToolCallRecord,
    compute_mission_outcome,
    mission_footer,
)
from .verify_core import VerifierOutcome


class TestVerbDetection(unittest.TestCase):
    """Multilingual verb -> kind mapping."""

    def test_open_spanish(self):
        outs = _detect_outcomes_in_clause("abrime el bloc de notas")
        self.assertIn("open_target", {o.kind for o in outs})

    def test_open_english(self):
        outs = _detect_outcomes_in_clause("open notepad")
        self.assertIn("open_target", {o.kind for o in outs})

    def test_close(self):
        outs = _detect_outcomes_in_clause("cerra steam")
        self.assertIn("close_target", {o.kind for o in outs})

    def test_filesystem_write(self):
        outs = _detect_outcomes_in_clause("creame un archivo nuevo")
        self.assertIn("filesystem_write", {o.kind for o in outs})

    def test_filesystem_read(self):
        outs = _detect_outcomes_in_clause("leeme el archivo notes.txt")
        self.assertIn("filesystem_read", {o.kind for o in outs})

    def test_search(self):
        outs = _detect_outcomes_in_clause("busca hollow knight en steam")
        self.assertIn("navigate", {o.kind for o in outs})

    def test_install(self):
        outs = _detect_outcomes_in_clause("instala discord")
        self.assertIn("destructive_install", {o.kind for o in outs})

    def test_delete(self):
        outs = _detect_outcomes_in_clause("borra esos archivos")
        self.assertIn("destructive_delete", {o.kind for o in outs})

    def test_play_media_priority(self):
        # "pon un video" debe ser open_target (media), no fallback
        outs = _detect_outcomes_in_clause("pon un video de gatos")
        kinds = {o.kind for o in outs}
        self.assertIn("open_target", kinds)


class TestSplitClauses(unittest.TestCase):
    """Multistep separator splitting."""

    def test_comma(self):
        clauses = _split_clauses("abri steam, busca hollow knight")
        self.assertEqual(len(clauses), 2)

    def test_y(self):
        clauses = _split_clauses("abri steam y cerra discord")
        self.assertEqual(len(clauses), 2)

    def test_then(self):
        clauses = _split_clauses("open notepad then type hello")
        self.assertEqual(len(clauses), 2)

    def test_accents_folded(self):
        clauses = _split_clauses("abri steam después cierra todo")
        # "después" or "despues" both separators
        self.assertGreaterEqual(len(clauses), 2)

    def test_empty(self):
        self.assertEqual(_split_clauses(""), [])
        self.assertEqual(_split_clauses("   "), [])


class TestKindsForCall(unittest.TestCase):
    """Arg-aware tool -> kind dispatch."""

    def test_app_open(self):
        kinds = _kinds_for_call("app", {"action": "open", "name": "Steam"})
        self.assertIn("open_target", kinds)
        self.assertNotIn("destructive_delete", kinds)

    def test_app_close(self):
        kinds = _kinds_for_call("app", {"action": "close", "name": "Steam"})
        self.assertIn("close_target", kinds)

    def test_app_search_is_read_only(self):
        kinds = _kinds_for_call("app", {"action": "search", "query": "Steam"})
        # search no abre nada — solo navega / lee.
        self.assertNotIn("open_target", kinds)
        self.assertIn("read_state", kinds)

    def test_app_uninstall_is_destructive(self):
        kinds = _kinds_for_call("app", {"action": "uninstall", "name": "X"})
        self.assertIn("destructive_delete", kinds)

    def test_steam_install_is_destructive(self):
        kinds = _kinds_for_call("steam", {"action": "install", "appid": "12345"})
        self.assertIn("destructive_install", kinds)

    def test_steam_search_store_is_navigate_only(self):
        kinds = _kinds_for_call("steam", {"action": "search_store", "query": "X"})
        self.assertIn("navigate", kinds)
        # NO debe satisfacer open_target ni destructive_install — la busqueda
        # NO abre el target ni instala.
        self.assertNotIn("destructive_install", kinds)

    def test_steam_launch_opens_target(self):
        kinds = _kinds_for_call("steam", {"action": "launch_game", "name": "X"})
        self.assertIn("open_target", kinds)

    def test_filesystem_write(self):
        kinds = _kinds_for_call("filesystem", {"action": "write", "path": "x.txt"})
        self.assertIn("filesystem_write", kinds)

    def test_filesystem_read(self):
        kinds = _kinds_for_call("filesystem", {"action": "read", "path": "x.txt"})
        self.assertIn("filesystem_read", kinds)

    def test_filesystem_delete(self):
        kinds = _kinds_for_call("filesystem", {"action": "delete", "path": "x"})
        self.assertIn("destructive_delete", kinds)
        # delete is not write
        self.assertNotIn("filesystem_write", kinds)

    def test_gui_click_install(self):
        kinds = _kinds_for_call("gui", {"action": "click", "target": "Install"})
        self.assertIn("destructive_install", kinds)

    def test_gui_click_normal(self):
        kinds = _kinds_for_call("gui", {"action": "click", "target": "OK"})
        self.assertIn("navigate", kinds)
        self.assertNotIn("destructive_install", kinds)

    def test_audio_set_volume(self):
        kinds = _kinds_for_call("audio", {"action": "set_volume", "level": 50})
        self.assertIn("set_state", kinds)

    def test_audio_get_volume_is_read(self):
        kinds = _kinds_for_call("audio", {"action": "get_volume"})
        self.assertIn("read_state", kinds)
        self.assertNotIn("set_state", kinds)


class TestMissionGoal(unittest.TestCase):
    """End-to-end MissionGoal usage."""

    def setUp(self):
        os.environ.pop("GEMMA4_MISSION_OFF", None)

    def test_simple_open(self):
        g = MissionGoal.from_user_text("abrime steam")
        self.assertGreaterEqual(len(g.expected), 1)
        self.assertEqual(g.expected[0].kind, "open_target")
        self.assertFalse(g.is_fulfilled())

        g.update_with_tool("app", {"action": "open", "name": "Steam"}, ok=True)
        self.assertTrue(g.is_fulfilled())

    def test_multistep_fulfillment(self):
        g = MissionGoal.from_user_text("abri steam y busca hollow knight")
        # Espera open_target + navigate (al menos)
        kinds = {o.kind for o in g.expected}
        self.assertIn("open_target", kinds)
        self.assertIn("navigate", kinds)

        # Solo la apertura — parcial
        g.update_with_tool("app", {"action": "open", "name": "Steam"}, ok=True)
        self.assertFalse(g.is_fulfilled())
        s, t = g.progress()
        self.assertEqual(s, 1)
        self.assertGreaterEqual(t, 2)

        # Ahora la busqueda — fulfilled
        g.update_with_tool("steam", {"action": "search_store", "query": "Hollow Knight"}, ok=True)
        self.assertTrue(g.is_fulfilled())

    def test_search_does_not_satisfy_open(self):
        # Si el usuario dijo "abri X" y el agente solo hizo search,
        # NO debe quedar fulfilled.
        g = MissionGoal.from_user_text("abrime hollow knight")
        g.update_with_tool("steam", {"action": "search_store", "query": "Hollow Knight"}, ok=True)
        self.assertFalse(g.is_fulfilled())

    def test_failed_tool_marks_unfulfilled(self):
        g = MissionGoal.from_user_text("abrime steam")
        g.update_with_tool("app", {"action": "open", "name": "Steam"}, ok=False)
        # matched_by != None pero confirmed=False -> NO fulfilled
        self.assertFalse(g.is_fulfilled())

    def test_missing_kinds_reported(self):
        g = MissionGoal.from_user_text("abri steam y borra el archivo X")
        self.assertIn("destructive_delete", {o.kind for o in g.expected})
        g.update_with_tool("app", {"action": "open", "name": "Steam"}, ok=True)
        missing = g.missing_kinds()
        self.assertIn("destructive_delete", missing)

    def test_summary_partial(self):
        g = MissionGoal.from_user_text("abri steam y borrame X")
        g.update_with_tool("app", {"action": "open", "name": "Steam"}, ok=True)
        s = g.summary()
        self.assertIn("parcial", s)
        self.assertIn("borrado", s)

    def test_empty_user_text(self):
        g = MissionGoal.from_user_text("")
        self.assertEqual(g.expected, [])
        self.assertFalse(g.is_fulfilled())

    def test_opt_out(self):
        os.environ["GEMMA4_MISSION_OFF"] = "1"
        try:
            g = MissionGoal.from_user_text("abri steam")
            self.assertEqual(g.expected, [])
        finally:
            os.environ.pop("GEMMA4_MISSION_OFF", None)


class TestComputeMissionOutcome(unittest.TestCase):
    """compute_mission_outcome status decision tests."""

    def setUp(self):
        os.environ.pop("GEMMA4_MISSION_OFF", None)

    def _verifier(self, name: str, confirmed: bool | None) -> VerifierOutcome:
        return VerifierOutcome(tool_name=name, confirmed=confirmed, reason="test")

    def test_no_tools_no_action_expected(self):
        # User pregunta algo conversacional — no se espera action.
        g = MissionGoal.from_user_text("que hora es")
        out = compute_mission_outcome(g, [], "Son las 12:30")
        # "que hora es" detecta read_state, no action_kind.
        self.assertEqual(out.status, OutcomeStatus.UNVERIFIED)

    def test_no_tools_action_expected(self):
        g = MissionGoal.from_user_text("abrime steam")
        out = compute_mission_outcome(g, [], "")
        self.assertEqual(out.status, OutcomeStatus.INTENT_NOT_FULFILLED)

    def test_completed(self):
        g = MissionGoal.from_user_text("abrime steam")
        g.update_with_tool("app", {"action": "open", "name": "Steam"}, ok=True)
        records = [_ToolCallRecord("app", {"action": "open"}, True, self._verifier("app", True))]
        out = compute_mission_outcome(g, records, "Listo")
        self.assertEqual(out.status, OutcomeStatus.COMPLETED)

    def test_partial(self):
        g = MissionGoal.from_user_text("abri steam y borrame X")
        g.update_with_tool("app", {"action": "open", "name": "Steam"}, ok=True)
        records = [_ToolCallRecord("app", {"action": "open"}, True, self._verifier("app", True))]
        out = compute_mission_outcome(g, records, "")
        self.assertEqual(out.status, OutcomeStatus.PARTIAL)

    def test_failed(self):
        g = MissionGoal.from_user_text("abrime steam")
        g.update_with_tool("app", {"action": "open", "name": "Steam"}, ok=False)
        records = [_ToolCallRecord("app", {"action": "open"}, False, self._verifier("app", False))]
        out = compute_mission_outcome(g, records, "")
        self.assertEqual(out.status, OutcomeStatus.FAILED)

    def test_disabled(self):
        os.environ["GEMMA4_MISSION_OFF"] = "1"
        try:
            g = MissionGoal.from_user_text("abri steam")
            out = compute_mission_outcome(g, [], "")
            self.assertEqual(out.status, OutcomeStatus.UNVERIFIED)
        finally:
            os.environ.pop("GEMMA4_MISSION_OFF", None)


class TestMissionFooter(unittest.TestCase):
    """mission_footer formatting rules."""

    def test_completed_no_footer(self):
        from .mission_goal import MissionOutcome
        out = MissionOutcome(
            status=OutcomeStatus.COMPLETED,
            summary="ok", confirmed_count=1, unverified_count=0,
        )
        self.assertEqual(mission_footer(out), "")

    def test_partial_has_footer(self):
        from .mission_goal import MissionOutcome
        out = MissionOutcome(
            status=OutcomeStatus.PARTIAL,
            summary="parcial (1/2)", expected_total=2, expected_satisfied=1,
        )
        self.assertIn("misión", mission_footer(out))
        self.assertIn("parcial", mission_footer(out))

    def test_unverified_no_expected_no_footer(self):
        from .mission_goal import MissionOutcome
        out = MissionOutcome(
            status=OutcomeStatus.UNVERIFIED,
            summary="conversacional", expected_total=0,
        )
        self.assertEqual(mission_footer(out), "")


if __name__ == "__main__":
    unittest.main()
