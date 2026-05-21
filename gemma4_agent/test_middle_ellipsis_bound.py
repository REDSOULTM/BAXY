"""middle_ellipsis is the core truncation primitive for ALL history compaction.
It had two bugs that made it FAIL to shrink (or GROW) content for small/moderate
limits — directly undermining context-overflow prevention:
  1. `text[-0:]` is the whole string (Python slicing gotcha), so when the tail
     budget hit 0 it returned head + marker + FULL text -> output LONGER than
     input.
  2. Fixed marker overhead pushed the result over `limit` for small limits.
These tests pin "output never exceeds limit (+marker) and never exceeds input"."""
from __future__ import annotations

import unittest

from gemma4_agent.agent_compaction import (
    HISTORY_TEXT_LIMIT,
    TOOL_RESULT_LIMIT,
    middle_ellipsis,
)


class TestMiddleEllipsisBound(unittest.TestCase):
    def test_output_never_exceeds_input(self):
        text = "A" * 400
        for limit in (5, 10, 50, 79, 100, 160, 200, 300, 500, 1000):
            out = middle_ellipsis(text, limit)
            self.assertLessEqual(
                len(out), len(text) + 1,
                f"limit={limit}: middle_ellipsis must never GROW the text "
                f"(was {len(out)} vs input {len(text)})")

    def test_output_bounded_by_limit(self):
        text = "X" * 1000
        for limit in (50, 100, 160, 300, 700):
            out = middle_ellipsis(text, limit)
            # Allow a small marker slack, but it must be in the limit ballpark
            # (the old bug returned 200-335 chars for these limits).
            self.assertLessEqual(len(out), limit + 5,
                                 f"limit={limit}: output {len(out)} exceeds bound")

    def test_short_text_unchanged(self):
        self.assertEqual(middle_ellipsis("hola", 100), "hola")

    def test_empty_and_zero(self):
        self.assertEqual(middle_ellipsis("", 100), "")
        self.assertEqual(middle_ellipsis("abc" * 100, 0), "")

    def test_keeps_head_and_tail_for_large_limit(self):
        text = "HEAD" + "m" * 400 + "TAIL"
        out = middle_ellipsis(text, 200)
        self.assertTrue(out.startswith("HEAD"))
        self.assertTrue(out.rstrip().endswith("TAIL"))
        self.assertIn("omitted", out)

    def test_real_module_limits_shrink(self):
        # The limits actually used in production must shrink an over-long input.
        big = "z" * (HISTORY_TEXT_LIMIT * 2)
        self.assertLess(len(middle_ellipsis(big, HISTORY_TEXT_LIMIT)),
                        len(big))
        self.assertLess(len(middle_ellipsis(big, TOOL_RESULT_LIMIT)),
                        len(big))


if __name__ == "__main__":
    unittest.main()
