"""Regression tests for the session-847 audit fixes.

Scope: everything that can be verified without a live LLM. The
LLM-classification side is exercised in test_session847_multilingual.py
(opt-in, slow).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .grounding_gate import (
    _FALLBACKS_BY_LANG,
    detect_reply_language,
    format_fallback,
)
from .intent_validator import (
    CROSS_REJECT_PAIRS,
    INTENT_TAG_INSTRUCTION,
    extract_intent_tag,
    needs_intent_tag,
    strip_intent_tag,
    validate_call,
)
from .planner import MAX_SELECTED_TOOLS, plan_mission, select_tool_names


class TestCancelTurnInSubset(unittest.TestCase):
    """Bug 2: session.cancel_turn must always be reachable to the LLM."""

    def _subset(self, query: str) -> list[str]:
        return select_tool_names(query, plan_mission(query), safety_enabled=False)

    def test_session_present_on_normal_turn(self):
        self.assertIn("session", self._subset("abre Steam"))

    def test_session_present_on_streaming_turn(self):
        self.assertIn("session", self._subset("pon Daredevil en Disney"))

    def test_session_present_on_smalltalk(self):
        # Smalltalk used to return [] which would deprive the LLM of
        # cancel_turn. The smalltalk path now seeds ["session"].
        self.assertEqual(self._subset("hola"), ["session"])

    def test_session_present_on_bare_cancel_word(self):
        self.assertIn("session", self._subset("tiempo"))
        self.assertIn("session", self._subset("stop"))
        self.assertIn("session", self._subset("nevermind"))
        self.assertIn("session", self._subset("lascia perdere"))

    def test_subset_within_cap(self):
        # session appended after _cap_tools, so a maximally crowded turn
        # ends at MAX_SELECTED_TOOLS + 1.
        subset = self._subset(
            "abre Steam, pon música en Spotify, busca en YouTube, "
            "lee este pdf, manda mensaje en WhatsApp, verifica la app"
        )
        self.assertLessEqual(len(subset), MAX_SELECTED_TOOLS + 1)


def _make_tool_registry(tmp_path: Path):
    from .memory import MemoryStore
    from .tools import ToolRegistry
    memory = MemoryStore(path=tmp_path / "memory.json")
    return ToolRegistry(memory=memory, captures_dir=tmp_path, safety_enabled=False)


class TestSchemaEnforcement(unittest.TestCase):
    """Bug 3: audio.set_volume rejects non-int / out-of-range level."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tools = _make_tool_registry(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_string_level_rejected(self):
        result = self.tools.execute("audio", {"action": "set_volume", "level": "10%"})
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "invalid tool arguments")
        errs = " ".join(result.get("validation_errors") or [])
        self.assertIn("level", errs)

    def test_out_of_range_rejected(self):
        result = self.tools.execute("audio", {"action": "set_volume", "level": 150})
        self.assertFalse(result.get("ok"))
        errs = " ".join(result.get("validation_errors") or [])
        self.assertIn("100", errs)

    def test_negative_rejected(self):
        result = self.tools.execute("audio", {"action": "set_volume", "level": -5})
        self.assertFalse(result.get("ok"))
        errs = " ".join(result.get("validation_errors") or [])
        self.assertIn(">= 0", errs)


class TestSessionToolImpl(unittest.TestCase):
    """Bug 2: session.cancel_turn is registered and idempotent."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tools = _make_tool_registry(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_cancel_turn_returns_ok(self):
        result = self.tools.execute("session", {"action": "cancel_turn"})
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("action"), "cancel_turn")
        self.assertEqual(result.get("completion_status"), "turn_cancelled")

    def test_unknown_action(self):
        result = self.tools.execute("session", {"action": "make_coffee"})
        self.assertFalse(result.get("ok"))


class TestIntentValidator(unittest.TestCase):
    """Bug 1 + validator: the tag parser, the reject table, and retry hint."""

    def test_tag_round_trip(self):
        reply = 'Reading user request. <intent>{"intent_type":"close","target":"YouTube"}</intent> ok.'
        tag = extract_intent_tag(reply)
        self.assertIsNotNone(tag)
        self.assertEqual(tag.intent_type, "close")
        self.assertEqual(tag.target, "YouTube")
        stripped = strip_intent_tag(reply)
        self.assertNotIn("<intent>", stripped)

    def test_tag_missing(self):
        self.assertIsNone(extract_intent_tag("no tag here"))

    def test_tag_bad_json(self):
        self.assertIsNone(extract_intent_tag("<intent>not json</intent>"))

    def test_needs_intent_tag_audio_vs_window(self):
        self.assertTrue(needs_intent_tag(["audio", "window", "verify"]))
        self.assertFalse(needs_intent_tag(["window", "verify"]))
        self.assertFalse(needs_intent_tag(["audio", "verify"]))

    def test_validator_rejects_known_bad_pair(self):
        tag = extract_intent_tag('<intent>{"intent_type":"close","target":"YouTube"}</intent>')
        result = validate_call(tag, "audio", {"action": "media_stop"})
        self.assertTrue(result.rejected)
        self.assertIn("close a window", result.reason.lower())

    def test_validator_accepts_correct_pair(self):
        tag = extract_intent_tag('<intent>{"intent_type":"close","target":"YouTube"}</intent>')
        result = validate_call(tag, "window", {"action": "close", "query": "YouTube"})
        self.assertFalse(result.rejected)

    def test_validator_passes_when_no_tag(self):
        result = validate_call(None, "audio", {"action": "media_stop"})
        self.assertFalse(result.rejected)

    def test_intent_tag_instruction_includes_format(self):
        self.assertIn("<intent>", INTENT_TAG_INSTRUCTION)
        self.assertIn("intent_type", INTENT_TAG_INSTRUCTION)

    def test_known_pairs_have_reasons(self):
        for key, reason in CROSS_REJECT_PAIRS.items():
            self.assertEqual(len(key), 3)
            self.assertTrue(reason, f"empty reason for {key}")


class TestLanguageAwareFallback(unittest.TestCase):
    """Bug 5: fallback respects the language of the rejected LLM reply."""

    def test_detects_spanish(self):
        self.assertEqual(detect_reply_language("Listo, abrí YouTube"), "es")

    def test_detects_english(self):
        self.assertEqual(detect_reply_language("Done, I opened YouTube for you"), "en")

    def test_detects_italian(self):
        self.assertEqual(detect_reply_language("Fatto, ho aperto YouTube"), "it")

    def test_detects_german(self):
        self.assertEqual(detect_reply_language("Fertig, ich habe YouTube geöffnet"), "de")

    def test_format_in_english(self):
        out = format_fallback(reason="generic", reply_lang_hint="en", rejected_reply="")
        self.assertEqual(out, _FALLBACKS_BY_LANG["en"]["generic"])

    def test_format_retry_has_hints(self):
        out = format_fallback(
            reason="retry", reply_lang_hint="es", rejected_reply="",
            hints="audio, window, media",
        )
        self.assertIn("audio, window, media", out)

    def test_format_partial_has_missing(self):
        out = format_fallback(
            reason="partial", reply_lang_hint="en", rejected_reply="",
            missing="contact, body",
        )
        self.assertIn("contact, body", out)

    def test_unknown_lang_falls_back_to_es(self):
        out = format_fallback(reason="generic", reply_lang_hint="xx", rejected_reply="")
        self.assertEqual(out, _FALLBACKS_BY_LANG["es"]["generic"])


class TestPhraseFireSuppressesSession(unittest.TestCase):
    """Bug 2 (revised): a fired phrase routine must keep cancel_turn out of
    the subset for that turn, so the LLM confirms the routine instead of
    proposing a cancellation."""

    def test_suppression_runs_in_run_content(self):
        # We don't run the LLM here — we just assert the public attribute
        # behavior: with non-empty _phrase_fires, the subset-filter code
        # path in agent.run_content removes 'session'.
        # This is the smallest meaningful assertion without a live LLM.
        from .agent import Gemma4Agent
        # Validate the snippet exists in the source (lightweight contract test):
        import inspect
        src = inspect.getsource(Gemma4Agent.run_content)
        self.assertIn("session_suppressed_by_phrase_fire", src)
        self.assertIn('"session" in selected_tool_names', src)


class TestToolDescriptionsRewrite(unittest.TestCase):
    """Bug 1 / Bug 3 / Bug 4: descriptions explicitly cover the failure
    modes from the log so the LLM has the guidance it lacked."""

    def setUp(self):
        from .tools import COMPOUND_TOOL_SCHEMAS
        self.by_name = {
            s["function"]["name"]: s["function"]
            for s in COMPOUND_TOOL_SCHEMAS
            if isinstance(s, dict) and isinstance(s.get("function"), dict)
        }

    def test_audio_description_warns_against_close(self):
        desc = self.by_name["audio"]["description"]
        # Negative example with cierra / close / schließ:
        self.assertIn("cierra YouTube", desc)
        self.assertRegex(desc, r"window\.close|browser_real\.tab_close|app\.close")

    def test_audio_set_volume_schema_has_range(self):
        params = self.by_name["audio"]["parameters"]
        level = params["properties"]["level"]
        self.assertEqual(level.get("type"), "integer")
        self.assertEqual(level.get("minimum"), 0)
        self.assertEqual(level.get("maximum"), 100)

    def test_window_description_lists_close_examples(self):
        desc = self.by_name["window"]["description"]
        # At least 3 languages — ES + IT/DE/EN — present in the close examples.
        self.assertIn("cierra", desc.lower())
        self.assertIn("close", desc.lower())
        # one of de/it should also be there:
        self.assertTrue("schließ" in desc.lower() or "chiudi" in desc.lower())

    def test_whatsapp_description_has_slot_filling(self):
        desc = self.by_name["whatsapp"]["description"]
        self.assertIn("SLOT FILLING", desc)
        self.assertIn("dile amor", desc)

    def test_session_tool_exists(self):
        self.assertIn("session", self.by_name)
        self.assertIn("cancel_turn", self.by_name["session"]["description"])


if __name__ == "__main__":
    unittest.main()
