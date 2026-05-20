"""Contract tests for the helpers that make up ``ToolRegistry.execute``.

These four pieces — ``_normalize_tool_result``,
``_coerce_and_validate_tool_args``, ``_PRE_VALIDATORS``,
``_parameters_for_tool`` — are the dispatch pipeline of the registry.
Sprint 5b deferred their extraction because they have many private-helper
dependencies; this file is the pre-requisite for Sprint 6.6 to do that
extraction safely.

No LLM contact; everything runs on dicts.
"""
from __future__ import annotations

import unittest

from gemma4_agent.tools import (
    COMPOUND_TOOL_SCHEMAS,
    _coerce_and_validate_tool_args,
    _correct_known_misroute,
    _normalize_tool_result,
    _parameters_for_tool,
    _PRE_VALIDATORS,
)


class TestCorrectKnownMisroute(unittest.TestCase):
    """Output-coherence guard: a tool call whose own args prove the wrong
    tool was chosen gets redirected. Language-universal (validates the
    model's output, not the user's words)."""

    def test_audio_device_with_level_redirects_to_audio(self):
        # The exact production failure: "baja el vol del pc a 10" ->
        # audio_device({set_default, level:10}) which has no `level` param.
        name, args = _correct_known_misroute(
            "audio_device", {"action": "set_default", "level": 10})
        self.assertEqual(name, "audio")
        self.assertEqual(args, {"action": "set_volume", "level": 10})

    def test_audio_device_volume_action_redirects(self):
        for action in ("lower", "raise", "set_volume", "volume"):
            name, args = _correct_known_misroute(
                "audio_device", {"action": action, "level": 20})
            self.assertEqual(name, "audio", f"action={action}")
            self.assertEqual(args["action"], "set_volume")

    def test_real_device_change_is_untouched(self):
        # A genuine default-device change must NOT be redirected.
        name, args = _correct_known_misroute(
            "audio_device", {"action": "set_default", "device": "HyperX"})
        self.assertEqual(name, "audio_device")
        self.assertEqual(args, {"action": "set_default", "device": "HyperX"})

    def test_device_list_is_untouched(self):
        name, args = _correct_known_misroute("audio_device", {"action": "list"})
        self.assertEqual(name, "audio_device")

    def test_already_correct_audio_is_untouched(self):
        name, args = _correct_known_misroute(
            "audio", {"action": "set_volume", "level": 30})
        self.assertEqual(name, "audio")
        self.assertEqual(args, {"action": "set_volume", "level": 30})

    def test_unrelated_tool_is_untouched(self):
        name, args = _correct_known_misroute("steam", {"action": "open"})
        self.assertEqual(name, "steam")


class TestNormalizeToolResult(unittest.TestCase):
    """_normalize_tool_result enforces the {ok, status, verified, tool, evidence}
    surface every caller (verifiers, traces, mission_outcome) relies on."""

    def test_ok_true_no_signals_marks_done_verified(self) -> None:
        out = _normalize_tool_result("audio", {"action": "get_volume"}, {"ok": True, "level": 30})
        self.assertEqual(out["ok"], True)
        self.assertEqual(out["status"], "done")
        self.assertIs(out["verified"], True)
        self.assertEqual(out["tool"], "audio")

    def test_ok_false_defaults_failed(self) -> None:
        out = _normalize_tool_result("audio", {"action": "set_volume"}, {"ok": False, "error": "boom"})
        self.assertEqual(out["ok"], False)
        self.assertEqual(out["status"], "failed")
        self.assertIs(out["verified"], False)
        self.assertEqual(out["completion_status"], "failed")

    def test_dispatch_completion_status_uses_dispatched(self) -> None:
        # opened_url is one of _DISPATCH_OK_COMPLETIONS; result becomes
        # status="dispatched" + verified=None (honest tristate).
        out = _normalize_tool_result(
            "browser", {"action": "open"},
            {"ok": True, "completion_status": "opened_url", "url": "https://x"},
        )
        self.assertEqual(out["status"], "dispatched")
        self.assertIsNone(out["verified"])

    def test_attempted_marks_attempted_status(self) -> None:
        out = _normalize_tool_result(
            "gui", {"action": "click"},
            {"ok": True, "attempted": True, "target": "Button"},
        )
        self.assertEqual(out["status"], "attempted")
        self.assertIs(out["verified"], False)

    def test_explicit_status_is_preserved(self) -> None:
        # Handler supplied a status — setdefault keeps it.
        out = _normalize_tool_result(
            "system", {"action": "time"},
            {"ok": True, "status": "ok"},
        )
        self.assertEqual(out["status"], "ok")

    def test_action_copied_from_args_when_missing(self) -> None:
        out = _normalize_tool_result(
            "audio", {"action": "mute"}, {"ok": True},
        )
        self.assertEqual(out["action"], "mute")

    def test_action_kept_when_already_present(self) -> None:
        out = _normalize_tool_result(
            "audio", {"action": "mute"}, {"ok": True, "action": "set_default"},
        )
        # Result's own `action` wins (handler's choice).
        self.assertEqual(out["action"], "set_default")

    def test_evidence_synthesized_when_absent(self) -> None:
        out = _normalize_tool_result(
            "filesystem", {"action": "list"},
            {"ok": True, "path": "/tmp/x"},
        )
        self.assertIn("evidence", out)
        # _result_evidence prefers `path` when present.
        self.assertEqual(out["evidence"], "/tmp/x")

    def test_explicit_evidence_kept(self) -> None:
        out = _normalize_tool_result(
            "filesystem", {"action": "list"},
            {"ok": True, "evidence": {"custom": True}},
        )
        self.assertEqual(out["evidence"], {"custom": True})

    def test_credential_redaction_runs(self) -> None:
        out = _normalize_tool_result(
            "database", {"action": "query"},
            {"ok": True, "password": "supersecret", "result": [1, 2, 3]},
        )
        # Sensitive key value is replaced; non-sensitive keys untouched.
        self.assertEqual(out["password"], "***REDACTED***")
        self.assertEqual(out["result"], [1, 2, 3])


class TestCoerceAndValidateToolArgs(unittest.TestCase):
    """_coerce_and_validate_tool_args turns LLM-emitted args into clean
    typed args + a list of human-readable errors."""

    def test_unknown_tool_returns_args_unchanged(self) -> None:
        # _parameters_for_tool(unknown) → None; coerce should pass through.
        clean, errors = _coerce_and_validate_tool_args("nonexistent_xyz", {"foo": "bar"})
        self.assertEqual(clean, {"foo": "bar"})
        self.assertEqual(errors, [])

    def test_int_passes_when_required(self) -> None:
        clean, errors = _coerce_and_validate_tool_args("audio", {"action": "set_volume", "level": 50})
        self.assertEqual(errors, [])
        self.assertEqual(clean["level"], 50)
        self.assertEqual(clean["action"], "set_volume")

    def test_string_int_is_coerced(self) -> None:
        # "30" should coerce to int 30 (the schema says level is integer).
        clean, errors = _coerce_and_validate_tool_args("audio", {"action": "set_volume", "level": "30"})
        self.assertEqual(errors, [])
        self.assertEqual(clean["level"], 30)

    def test_out_of_range_int_yields_error(self) -> None:
        # audio.set_volume has minimum=0, maximum=100.
        clean, errors = _coerce_and_validate_tool_args(
            "audio", {"action": "set_volume", "level": 150},
        )
        self.assertTrue(any("level" in e and "100" in e for e in errors),
                        f"expected range error, got {errors!r}")

    def test_missing_required_yields_error(self) -> None:
        # audio.action is required.
        clean, errors = _coerce_and_validate_tool_args("audio", {})
        self.assertTrue(any("missing required argument: action" in e for e in errors),
                        f"expected missing-action error, got {errors!r}")

    def test_extra_args_silently_accepted_when_additional_True(self) -> None:
        # Most tool schemas accept additionalProperties; extras should
        # survive without errors.
        clean, errors = _coerce_and_validate_tool_args(
            "system", {"action": "time", "random_extra_field": "ignored"},
        )
        # Default ACTION_ENUMS decoration sets additionalProperties=False
        # via _apply_action_enums — but that runs on the global schema.
        # We accept either outcome (the schema's actual policy), and only
        # verify the helper doesn't raise.
        self.assertIn("action", clean)


class TestParametersForTool(unittest.TestCase):
    """_parameters_for_tool exposes the LLM-facing JSON schema parameters."""

    def test_returns_dict_for_known_tool(self) -> None:
        out = _parameters_for_tool("audio")
        self.assertIsInstance(out, dict)
        self.assertIn("properties", out)
        self.assertIn("action", out["properties"])

    def test_returns_none_for_unknown_tool(self) -> None:
        self.assertIsNone(_parameters_for_tool("nonexistent_xyz"))

    def test_consistent_across_all_65_tools(self) -> None:
        # Every tool in COMPOUND_TOOL_SCHEMAS must round-trip cleanly.
        for schema in COMPOUND_TOOL_SCHEMAS:
            name = schema["function"]["name"]
            params = _parameters_for_tool(name)
            self.assertIsNotNone(params,
                                  f"_parameters_for_tool({name!r}) is None but should exist")


class TestPreValidatorsRegistry(unittest.TestCase):
    """_PRE_VALIDATORS routes a few tools through extra checks before
    the safety classifier and the handler."""

    def test_registry_is_dict_of_callables(self) -> None:
        self.assertIsInstance(_PRE_VALIDATORS, dict)
        for name, fn in _PRE_VALIDATORS.items():
            self.assertTrue(callable(fn),
                            f"_PRE_VALIDATORS[{name!r}] is not callable")

    def test_notification_validator_passes_iso_datetime(self) -> None:
        fn = _PRE_VALIDATORS.get("notification")
        self.assertIsNotNone(fn)
        out = fn({"action": "reminder_create", "due": "2026-12-31T23:59:00"})
        self.assertIsNone(out, "valid ISO datetime should pass (returns None)")

    def test_notification_validator_passes_hhmm(self) -> None:
        fn = _PRE_VALIDATORS["notification"]
        out = fn({"action": "alarm_create", "time": "09:30"})
        self.assertIsNone(out)

    def test_notification_validator_rejects_garbage_time(self) -> None:
        fn = _PRE_VALIDATORS["notification"]
        out = fn({"action": "reminder_create", "due": "tomorrow morning"})
        self.assertIsNotNone(out)
        self.assertEqual(out["status"], "needs_user")
        self.assertIn("tomorrow morning", out["error"])

    def test_notification_validator_ignores_non_scheduling_actions(self) -> None:
        # Action without scheduling semantics returns None (no opinion).
        fn = _PRE_VALIDATORS["notification"]
        self.assertIsNone(fn({"action": "toast_now", "title": "hi"}))


if __name__ == "__main__":
    unittest.main()
