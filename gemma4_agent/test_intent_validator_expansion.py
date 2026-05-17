"""Tests for the 4 new ambiguous-subset pairs + 6 new cross-reject
pairs added in hotfix F 2026-05-17.

These are language-agnostic by construction: the validator works
off the LLM's <intent> tag (abstract verbs), not user text.
"""
from __future__ import annotations

import unittest

from gemma4_agent.intent_validator import (
    CROSS_REJECT_PAIRS,
    IntentTag,
    needs_intent_tag,
    validate_call,
)


class AmbiguousSubsetTriggersTagTest(unittest.TestCase):
    def test_email_whatsapp_pair_triggers_intent_tag(self) -> None:
        self.assertTrue(needs_intent_tag(["email", "whatsapp", "session"]))

    def test_browser_browser_real_pair_triggers_intent_tag(self) -> None:
        self.assertTrue(needs_intent_tag(["browser", "browser_real", "session"]))

    def test_filesystem_download_pair_triggers_intent_tag(self) -> None:
        self.assertTrue(needs_intent_tag(["filesystem", "download", "session"]))

    def test_terminal_developer_pair_triggers_intent_tag(self) -> None:
        self.assertTrue(needs_intent_tag(["terminal", "developer", "session"]))

    def test_unrelated_subset_does_not_trigger(self) -> None:
        # Just session + a single non-ambiguous tool.
        self.assertFalse(needs_intent_tag(["session", "memory"]))

    def test_audio_pairs_still_trigger(self) -> None:
        # Hotfix F must not regress the original 4 pairs.
        self.assertTrue(needs_intent_tag(["audio", "window"]))
        self.assertTrue(needs_intent_tag(["audio", "media"]))


class CrossRejectPairReasonsTest(unittest.TestCase):
    def test_send_email_to_whatsapp_send_message_is_rejected(self) -> None:
        reason = CROSS_REJECT_PAIRS.get(("send_email", "whatsapp", "send_message"))
        self.assertIsNotNone(reason)
        self.assertIn("EMAIL", reason)

    def test_send_whatsapp_to_email_send_is_rejected(self) -> None:
        reason = CROSS_REJECT_PAIRS.get(("send_whatsapp", "email", "send"))
        self.assertIsNotNone(reason)
        self.assertIn("WhatsApp", reason)

    def test_automate_page_with_browser_open_is_rejected(self) -> None:
        reason = CROSS_REJECT_PAIRS.get(("automate_page", "browser", "open"))
        self.assertIsNotNone(reason)
        self.assertIn("browser_real", reason)

    def test_just_navigate_with_browser_real_click_is_rejected(self) -> None:
        reason = CROSS_REJECT_PAIRS.get(("just_navigate", "browser_real", "click"))
        self.assertIsNotNone(reason)

    def test_download_file_with_filesystem_copy_is_rejected(self) -> None:
        reason = CROSS_REJECT_PAIRS.get(("download_file", "filesystem", "copy"))
        self.assertIsNotNone(reason)

    def test_git_workflow_with_terminal_run_is_rejected(self) -> None:
        reason = CROSS_REJECT_PAIRS.get(("git_workflow", "terminal", "run"))
        self.assertIsNotNone(reason)
        self.assertIn("git", reason)


class ValidateCallEndToEndTest(unittest.TestCase):
    """Exercise validate_call with the new pairs to make sure the
    dispatcher actually rejects them in practice."""

    def test_send_email_intent_with_whatsapp_call_rejected(self) -> None:
        intent = IntentTag(
            intent_type="send_email", target="boss@example.com",
            raw="<intent>...</intent>",
        )
        result = validate_call(intent, "whatsapp", {"action": "send_message"})
        self.assertTrue(result.rejected)
        self.assertIn("EMAIL", result.reason)

    def test_automate_page_intent_with_browser_open_rejected(self) -> None:
        intent = IntentTag(
            intent_type="automate_page", target="https://x.com",
            raw="<intent>...</intent>",
        )
        result = validate_call(intent, "browser", {"action": "open"})
        self.assertTrue(result.rejected)


if __name__ == "__main__":
    unittest.main()
