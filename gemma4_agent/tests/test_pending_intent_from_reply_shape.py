"""When the LLM ends its reply with a question mark and didn't
fire any tool this turn, pending_intent gets set targeting the
first non-meta tool in the subset. The next turn's router will
inject that tool.

100% structural detection — no user text matching.
Hotfix I 2026-05-17.
"""
from __future__ import annotations

import unittest

from gemma4_agent.agent_core.agent import _should_set_pending_intent_from_reply


class PendingFromReplyShapeTest(unittest.TestCase):
    def _detect(
        self, reply: str, tool_calls: list, subset: list,
    ) -> tuple[str, str] | None:
        return _should_set_pending_intent_from_reply(reply, tool_calls, subset)

    def test_question_mark_es_inverted_triggers(self) -> None:
        # Spanish inverted question mark at start, ASCII '?' at end.
        r = self._detect("¿lo comprás o ya lo tenés?", [], ["steam", "session"])
        self.assertEqual(r, ("steam", "user_clarification"))

    def test_question_mark_en_triggers(self) -> None:
        r = self._detect("Do you own it already?", [], ["steam", "session"])
        self.assertEqual(r, ("steam", "user_clarification"))

    def test_question_mark_fr_triggers(self) -> None:
        # Cross-lingual: French question. Structural detection on
        # '?' char only — language-agnostic.
        r = self._detect("Voulez-vous l'acheter?", [], ["steam", "session"])
        self.assertEqual(r, ("steam", "user_clarification"))

    def test_question_mark_fullwidth_triggers(self) -> None:
        # CJK fullwidth question mark.
        r = self._detect("もう買いましたか？", [], ["steam", "session"])
        self.assertEqual(r, ("steam", "user_clarification"))

    def test_no_question_mark_does_not_trigger(self) -> None:
        r = self._detect("Listo, abrí Steam.", [], ["steam", "session"])
        self.assertIsNone(r)

    def test_successful_tool_call_blocks_trigger(self) -> None:
        # If a tool actually ran successfully, this is a normal
        # turn ending — don't stash a pending intent.
        calls = [{"tool": "steam", "result": {"ok": True}}]
        r = self._detect("¿algo más?", calls, ["steam", "session"])
        self.assertIsNone(r)

    def test_only_meta_subset_does_not_trigger(self) -> None:
        # No domain tool to target.
        r = self._detect("¿qué querés hacer?", [], ["session", "state"])
        self.assertIsNone(r)

    def test_unverified_tool_call_does_not_block_trigger(self) -> None:
        # ok=False tool call doesn't count as a successful action,
        # so the question-mark trigger still fires.
        calls = [{"tool": "steam", "result": {"ok": False, "error": "x"}}]
        r = self._detect("¿lo comprás?", calls, ["steam", "session"])
        self.assertEqual(r, ("steam", "user_clarification"))

    def test_targets_first_non_meta_tool(self) -> None:
        # 'session' is meta — should pick 'steam' as the target.
        r = self._detect(
            "¿qué hago?", [], ["session", "steam", "media"],
        )
        self.assertEqual(r, ("steam", "user_clarification"))

    def test_trailing_punctuation_stripped_before_check(self) -> None:
        # Reply ends with ?' (quote after question mark) — stripped
        # so the '?' is the effective terminal char.
        r = self._detect("'¿comprás?'", [], ["steam"])
        self.assertEqual(r, ("steam", "user_clarification"))

    def test_empty_reply_does_not_trigger(self) -> None:
        self.assertIsNone(self._detect("", [], ["steam"]))


if __name__ == "__main__":
    unittest.main()
