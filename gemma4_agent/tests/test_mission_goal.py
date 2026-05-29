"""Unit tests for mission_goal + mission_outcome (TIER 2 #5)."""
from __future__ import annotations

import os
import unittest

from ..mission.mission_goal import (
    MissionGoal,
    OutcomeStatus,
    _detect_outcomes_in_clause,
    _kinds_for_call,
    _split_clauses,
)
from ..mission.mission_outcome import (
    _ToolCallRecord,
    compute_mission_outcome,
    mission_footer,
)
from ..safety_pkg.verify_core import VerifierOutcome


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
    """mission_footer formatting rules.

    Post Fix N (2026-05-15 user feedback): el footer "[misión: ...]" NUNCA
    se inyecta al display, sin importar el status. mission_footer() devuelve
    siempre "". El outcome sigue persistiendo en trace para telemetry.
    """

    def test_footer_never_emitted_for_any_status(self):
        from ..mission.mission_goal import MissionOutcome
        statuses = [
            OutcomeStatus.COMPLETED,
            OutcomeStatus.PARTIAL,
            OutcomeStatus.FAILED,
            OutcomeStatus.UNVERIFIED,
            OutcomeStatus.NEEDS_USER,
            OutcomeStatus.INTENT_NOT_FULFILLED,
            OutcomeStatus.TOOL_OK_VERIFIER_INCONCLUSIVE,
            OutcomeStatus.NEEDS_PERMISSION,
            OutcomeStatus.BLOCKED_BY_POLICY,
        ]
        for status in statuses:
            out = MissionOutcome(
                status=status,
                summary="cualquier resumen", expected_total=2, expected_satisfied=1,
            )
            self.assertEqual(
                mission_footer(out), "",
                f"footer debe ser vacio para status={status.value}",
            )


class TestBugFixes(unittest.TestCase):
    """Regression tests for bugs found in session 20:03-20:15 (2026-05-15)."""

    def test_smalltalk_no_expected_outcomes(self):
        """Bug B: 'Hablame en gitano' / 'Insultame' no deben tener expected outcomes."""
        for prompt in ("Hablame en gitano", "Insultame", "weona", "Como a Gemma"):
            g = MissionGoal.from_user_text(prompt)
            self.assertEqual(
                len(g.expected), 0,
                f"{prompt!r} no debe generar expected outcomes (got {[o.kind for o in g.expected]})",
            )

    def test_smalltalk_outcome_is_unverified_no_footer(self):
        """Bug A: smalltalk no debe emitir footer eco del reply."""
        g = MissionGoal.from_user_text("Insultame")
        out = compute_mission_outcome(g, [], "No estoy programado para insultar a nadie...")
        self.assertEqual(out.status, OutcomeStatus.UNVERIFIED)
        # Summary debe ser estructural, NO eco del reply.
        self.assertNotIn("No estoy programado", out.summary)
        # Footer silenciado.
        self.assertEqual(mission_footer(out), "")

    def test_strip_trailing_footers_idempotent(self):
        """Bug C: strip remueve footer y es idempotente."""
        from ..agent_core.agent import _strip_trailing_footers
        text_with = "Hola.\n\n[misión: sin objetivos detectados]"
        stripped = _strip_trailing_footers(text_with)
        self.assertEqual(stripped, "Hola.")
        # Idempotente
        self.assertEqual(_strip_trailing_footers(stripped), "Hola.")

    def test_strip_multiple_stacked_footers(self):
        """Bug C: multiple footers stackeados (verifier + mission) se strippean todos."""
        from ..agent_core.agent import _strip_trailing_footers
        text = ("Reply real del modelo.\n\n[1 no verificable(s)]"
                "\n\n[misión: parcial (1/2); falta: abrir lo que pediste]")
        stripped = _strip_trailing_footers(text)
        self.assertEqual(stripped, "Reply real del modelo.")

    def test_strip_preserves_normal_brackets(self):
        """No deber strippear texto que contiene brackets normales."""
        from ..agent_core.agent import _strip_trailing_footers
        text = "Aqui hay [info] en medio.\nFinal sin footer."
        self.assertEqual(_strip_trailing_footers(text), text.rstrip())

    def test_build_system_prompt_distinguishes_none_vs_empty(self):
        """Bug latencia: smalltalk con [] no debe inyectar TODAS las TOOL_RULES."""
        from ..agent_core.agent import build_system_prompt
        # 2026-05-21: build_system_prompt is now PROFILE-AWARE — smalltalk
        # returns the ACTIVE profile's CORE (lean on small-model tiers, full on
        # large). The invariant under test is unchanged: smalltalk == the bare
        # CORE with NO tool rules appended. So compare against the core the
        # builder actually selected, not the hardcoded full CORE_PROMPT.
        from ..agent_core.agent_prompt import _core_for_profile
        active_core = _core_for_profile()
        legacy = build_system_prompt(None)
        smalltalk = build_system_prompt([])
        subset = build_system_prompt(["app", "steam"])
        # legacy = CORE + TODAS las rules (~60+ rules concatenadas)
        # smalltalk = solo CORE (del perfil activo)
        # subset = CORE + reglas filtradas
        self.assertGreater(len(legacy), len(subset),
                           "legacy debe tener mas chars que subset")
        self.assertGreater(len(subset), len(smalltalk),
                           "subset debe tener mas chars que smalltalk (al menos las rules de app+steam)")
        self.assertEqual(smalltalk, active_core,
                         "smalltalk debe ser exactamente el CORE del perfil activo (sin rules)")

    def test_tool_schemas_hint_distinguishes_none_vs_empty(self):
        """Bug latencia: smalltalk con [] no debe inyectar TODOS los 63 schemas."""
        import os
        os.environ['GEMMA4_LLAMA_AUTO_START'] = '0'
        # Forzar el modo compact: en 'auto' el hint depende del ctx del perfil
        # activo (off si <12288), y vram12/16 ahora corren a 8192 -> auto daria
        # "". Este test verifica el contrato subset-vs-vacio, no el gate de ctx,
        # asi que fijamos el modo para que sea determinista.
        prev = os.environ.get('GEMMA4_TOOL_SCHEMAS_HINT_MODE')
        os.environ['GEMMA4_TOOL_SCHEMAS_HINT_MODE'] = 'compact'
        try:
            from ..agent_core.agent import Gemma4Agent
            from ..infra.config import AgentConfig
            agent = Gemma4Agent(AgentConfig.from_env())
            # selected = [] (smalltalk) -> sin hint
            h_empty = agent._tool_schemas_hint(selected_tool_names=[])
            self.assertEqual(h_empty, "",
                             "selected=[] (smalltalk) debe devolver hint vacio")
            # selected = ['app','steam'] -> hint con esos 2 tools
            h_subset = agent._tool_schemas_hint(selected_tool_names=['app', 'steam'])
            self.assertGreater(len(h_subset), 0)
            self.assertLess(len(h_subset), 10000,
                            "subset de 2 tools debe ser <10K chars (no full catalog)")
        finally:
            if prev is None:
                os.environ.pop('GEMMA4_TOOL_SCHEMAS_HINT_MODE', None)
            else:
                os.environ['GEMMA4_TOOL_SCHEMAS_HINT_MODE'] = prev


if __name__ == "__main__":
    unittest.main()
