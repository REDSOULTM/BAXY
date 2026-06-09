"""Tests for the 'dispatched' status + verified=None semantics fix.

Audit 2026-05-15 found 40+ false negatives where dispatch-by-nature tools
(browser.youtube_play, media.play_pause via media key, browser.open URL,
steam.store_page, app.open) reported verified=False and triggered the
"Nota: no dejo evidencia suficiente" guard even though the action succeeded.

This file tests the 3 layers of fix:
  1. _normalize_tool_result maps completion_status='opened_*' / 'sent_*' /
     'launch_requested' to status='dispatched' + verified=None.
  2. _guard_unverified_final does NOT inject "Nota:" for dispatched results.
  3. summarize_verifiers stays silent when only confirmed=None (no failed).
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("GEMMA4_LLAMA_AUTO_START", "0")

from ..agent_core.agent import Gemma4Agent, ToolEvent
from ..infra.config import AgentConfig
from ..tools_pkg.tools import _normalize_tool_result, _has_unverified_signal, _DISPATCH_OK_COMPLETIONS
from ..safety_pkg.verify_core import VerifierOutcome, summarize_verifiers


class TestNormalizeDispatched(unittest.TestCase):

    def test_youtube_play_becomes_dispatched(self):
        r = _normalize_tool_result(
            "browser", {"action": "youtube_play"},
            {
                "ok": True, "action": "youtube_play", "url": "https://yt/x",
                "opened": True, "playback_verified": False,
                "completion_status": "opened_youtube_video_for_playback",
            },
        )
        self.assertEqual(r["status"], "dispatched")
        self.assertIsNone(r["verified"])

    def test_browser_search_becomes_dispatched(self):
        r = _normalize_tool_result(
            "browser", {"action": "search"},
            {
                "ok": True, "url": "https://google.com/?q=x",
                "content_verified": False,
                "completion_status": "opened_search_results",
            },
        )
        self.assertEqual(r["status"], "dispatched")
        self.assertIsNone(r["verified"])

    def test_browser_open_url_becomes_dispatched(self):
        r = _normalize_tool_result(
            "browser", {"action": "open"},
            {
                "ok": True, "url": "https://store.steampowered.com/",
                "opened": True, "content_verified": False,
                "completion_status": "opened_url",
            },
        )
        self.assertEqual(r["status"], "dispatched")
        self.assertIsNone(r["verified"])

    def test_media_play_pause_becomes_dispatched(self):
        r = _normalize_tool_result(
            "audio", {"action": "media_play_pause"},
            {
                "ok": True, "action": "media_play_pause",
                "playback_verified": False,
                "completion_status": "sent_global_media_key",
            },
        )
        self.assertEqual(r["status"], "dispatched")
        self.assertIsNone(r["verified"])

    def test_web_failure_footer_suppressed_after_later_web_success(self):
        footer = summarize_verifiers([
            VerifierOutcome("web", False, "web read failed"),
            VerifierOutcome("web", True, "research returned 2 sources"),
        ])
        self.assertEqual(footer, "")

    def test_web_failure_footer_not_suppressed_by_other_tool_success(self):
        footer = summarize_verifiers([
            VerifierOutcome("web", False, "web read failed"),
            VerifierOutcome("app", True, "app opened"),
        ])
        self.assertIn("no pude confirmar", footer)

    def test_app_open_launch_requested_becomes_dispatched(self):
        r = _normalize_tool_result(
            "app", {"action": "open"},
            {
                "ok": True, "query": "Marvel Rivals",
                "completion_status": "launch_requested",
            },
        )
        self.assertEqual(r["status"], "dispatched")
        self.assertIsNone(r["verified"])

    def test_steam_store_page_becomes_dispatched(self):
        r = _normalize_tool_result(
            "steam", {"action": "store_page"},
            {
                "ok": True, "appid": "2767030", "uri": "steam://store/2767030",
                "opened_in": "steam_client", "visual_verified": False,
                "completion_status": "opened_steam_client_store_page",
            },
        )
        self.assertEqual(r["status"], "dispatched")
        self.assertIsNone(r["verified"])

    def test_genuine_unverified_stays_needs_verification(self):
        # gui.click_text con found=False es genuino needs_verification (no encontro).
        r = _normalize_tool_result(
            "gui", {"action": "click_text"},
            {
                "ok": True, "target": "Pantalla completa", "found": False,
                "content_verified": False, "visual_verified": False,
            },
        )
        self.assertNotEqual(r["status"], "dispatched")
        self.assertFalse(r["verified"])

    def test_genuine_done_stays_done(self):
        r = _normalize_tool_result(
            "system", {"action": "time"},
            {"ok": True, "iso": "2026-05-15T12:00:00"},
        )
        self.assertEqual(r["status"], "done")
        self.assertTrue(r["verified"])

    def test_failure_stays_failed(self):
        r = _normalize_tool_result(
            "app", {"action": "open"},
            {"ok": False, "error": "app not found"},
        )
        self.assertEqual(r["status"], "failed")
        self.assertFalse(r["verified"])

    def test_has_unverified_signal_filters_dispatch_ok(self):
        # opened_youtube_video_for_playback no debe contar como unverified.
        r = {
            "ok": True, "completion_status": "opened_youtube_video_for_playback",
            "playback_verified": False,
        }
        self.assertFalse(_has_unverified_signal(r))


class TestGuardUnverifiedFinal(unittest.TestCase):

    def setUp(self):
        self.agent = Gemma4Agent(AgentConfig.from_env())

    def _event(self, name: str, args: dict, raw_result: dict) -> ToolEvent:
        normalized = _normalize_tool_result(name, args, raw_result)
        return ToolEvent(name=name, args=args, result=normalized)

    def test_no_nota_for_youtube_play(self):
        event = self._event(
            "browser", {"action": "youtube_play"},
            {
                "ok": True, "url": "https://yt/x", "opened": True,
                "playback_verified": False,
                "completion_status": "opened_youtube_video_for_playback",
            },
        )
        out = self.agent._guard_unverified_final("Abri YouTube con gatos.", [event])
        self.assertNotIn("Nota:", out)
        self.assertEqual(out, "Abri YouTube con gatos.")

    def test_no_nota_for_browser_open_url(self):
        event = self._event(
            "browser", {"action": "open"},
            {
                "ok": True, "url": "https://store.steampowered.com/",
                "opened": True, "completion_status": "opened_url",
            },
        )
        out = self.agent._guard_unverified_final("Abri Steam Store.", [event])
        self.assertNotIn("Nota:", out)

    def test_no_nota_for_media_key(self):
        event = self._event(
            "audio", {"action": "media_play_pause"},
            {
                "ok": True, "playback_verified": False,
                "completion_status": "sent_global_media_key",
            },
        )
        out = self.agent._guard_unverified_final("Pause enviado.", [event])
        self.assertNotIn("Nota:", out)

    def test_no_nota_for_app_launch_requested(self):
        event = self._event(
            "app", {"action": "open"},
            {"ok": True, "query": "X", "completion_status": "launch_requested"},
        )
        out = self.agent._guard_unverified_final("Abriendo la app.", [event])
        self.assertNotIn("Nota:", out)

    def test_nota_still_emitted_for_genuine_failure(self):
        # Si la tool genuinamente fallo (gui.click_text con found=False),
        # SI queremos la nota DURA de no-confirmacion.
        event = self._event(
            "gui", {"action": "click_text"},
            {
                "ok": True, "target": "X", "found": False,
                "content_verified": False,
            },
        )
        out = self.agent._guard_unverified_final("Click hecho.", [event])
        # Genuine measured-fail (found=False) -> nota DURA.
        self.assertIn("Nota:", out)
        self.assertIn("no dejo evidencia suficiente", out.lower())
        self.assertNotIn("no pude confirmar el efecto", out.lower())

    def test_false_open_claim_replaced_on_measured_failure(self):
        event = self._event(
            "app", {"action": "search", "query": "Kai Cenat collab"},
            {
                "ok": True,
                "verified": False,
                "status": "needs_verification",
                "completion_status": "low_confidence_local_app_search",
                "evidence": "tool_result",
            },
        )
        out = self.agent._guard_unverified_final("Listo, abri Chrome.", [event])
        self.assertNotIn("abri Chrome", out)
        self.assertIn("No pude completar", out)
        self.assertIn("Nota:", out)

    def test_soft_note_for_unmeasured_steps(self):
        # TRI-ESTADO (2026-06-01): un plan computer_use con steps NO medibles
        # colapsa al top-level verified=False (PlanExecutor L1283) pero la verdad
        # vive en steps[*].verified=None. El guard debe leer steps y dar la nota
        # SUAVE ("no pude confirmar el efecto"), NUNCA afirmar fallo.
        event = ToolEvent(
            name="computer_use", args={"goal": "x"},
            result={
                "ok": True, "verified": False, "status": "attempted",
                "completion_status": "attempted",
                "steps": [{"op": "type", "verified": None, "state_changed": None},
                          {"op": "keypress", "verified": None, "state_changed": None}],
            },
        )
        out = self.agent._guard_unverified_final("Listo.", [event])
        self.assertIn("no pude confirmar el efecto", out.lower())
        self.assertNotIn("no dejo evidencia suficiente", out.lower())

    def test_fail_note_when_any_step_measured_false(self):
        # Mismo colapso, pero un step SÍ midió no-cambio -> fallo DURO.
        event = ToolEvent(
            name="computer_use", args={"goal": "x"},
            result={
                "ok": True, "verified": False, "status": "attempted",
                "completion_status": "attempted",
                "steps": [{"op": "click_button", "verified": False,
                           "state_changed": False}],
            },
        )
        out = self.agent._guard_unverified_final("Listo.", [event])
        self.assertIn("no dejo evidencia suficiente", out.lower())
        self.assertNotIn("no pude confirmar el efecto", out.lower())


class TestSummarizeVerifiersSilent(unittest.TestCase):

    def test_silent_when_only_unverifiable(self):
        outs = [
            VerifierOutcome("browser", None, "no_verifier_registered"),
            VerifierOutcome("media", None, "no_verifier_registered"),
        ]
        self.assertEqual(summarize_verifiers(outs), "")

    def test_silent_when_all_confirmed(self):
        outs = [VerifierOutcome("app", True, "app opened")]
        self.assertEqual(summarize_verifiers(outs), "")

    def test_silent_when_mix_confirmed_and_unverifiable(self):
        outs = [
            VerifierOutcome("app", True, "ok"),
            VerifierOutcome("browser", None, "no_verifier"),
        ]
        # Sin failed -> silencio.
        self.assertEqual(summarize_verifiers(outs), "")

    def test_emits_when_any_failed(self):
        # Footer ahora en PROSA honesta (no marker "[N no confirmada(s)]").
        outs = [VerifierOutcome("app", False, "app crashed")]
        f = summarize_verifiers(outs)
        self.assertIn("no pude confirmar", f.lower())
        self.assertNotIn("[", f)

    def test_emits_full_breakdown_when_failed_plus_other(self):
        outs = [
            VerifierOutcome("app", True, "ok"),
            VerifierOutcome("browser", False, "failed"),
            VerifierOutcome("media", None, "no_verifier"),
        ]
        f = summarize_verifiers(outs)
        # solo el failed se surfacea (en prosa); verificada/no-verificable no
        # ensucian el reply hablado.
        self.assertIn("no pude confirmar", f.lower())
        self.assertNotIn("[", f)


class TestDispatchCompletionsSet(unittest.TestCase):
    """Sanity: el set de completions OK incluye las que vimos en logs reales."""

    def test_includes_all_observed_dispatch_completions(self):
        observed_in_logs = {
            "opened_youtube_video_for_playback",
            "opened_search_results",
            "opened_url",
            "opened_steam_client_store_page",
            "opened_matching_steam_library_detail",
            "sent_global_media_key",
            "launch_requested",
        }
        for completion in observed_in_logs:
            self.assertIn(
                completion, _DISPATCH_OK_COMPLETIONS,
                f"{completion} should be in _DISPATCH_OK_COMPLETIONS",
            )


if __name__ == "__main__":
    unittest.main()
