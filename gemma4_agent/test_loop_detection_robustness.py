"""The loop detector is a SAFETY NET — it must never crash the turn it protects.
_result_signature / _hash_tool_call previously raised TypeError on a result/args
dict with mixed-type keys (both json.dumps(sort_keys=True) AND sorted(items())
raise), which would propagate into agent.run_content. These tests pin the
never-raise invariant on pathological inputs while keeping detection working."""
from __future__ import annotations

import unittest

from gemma4_agent.loop_detection import (
    LoopState,
    _hash_tool_call,
    _result_signature,
)


class TestSignatureNeverRaises(unittest.TestCase):
    PATHOLOGICAL = [
        {1: "a", "b": 2},            # mixed-type keys -> breaks sort
        {"x": object()},            # non-serializable value
        {"s": {1, 2, 3}},           # set value
        {"nested": {2: "two", "one": 1}},  # mixed-type nested keys
        {None: "n", (1, 2): "tuple-key"},  # exotic keys
    ]

    def test_result_signature_never_raises(self):
        for r in self.PATHOLOGICAL:
            sig = _result_signature(r)  # must not raise
            self.assertIsInstance(sig, str)
            self.assertTrue(sig)

    def test_hash_tool_call_never_raises(self):
        for a in self.PATHOLOGICAL:
            h = _hash_tool_call("some_tool", a)  # must not raise
            self.assertIsInstance(h, str)
            self.assertTrue(h)

    def test_record_with_pathological_result_does_not_raise(self):
        # The real path: record() calls both helpers. A weird tool result must
        # not crash the turn.
        st = LoopState()
        for r in self.PATHOLOGICAL:
            st.record("weird_tool", {"k": "v"}, exists=True, result=r)
        self.assertEqual(st.global_count, len(self.PATHOLOGICAL))


class TestDetectionStillWorks(unittest.TestCase):
    def test_identical_calls_still_hash_identically(self):
        # Same (tool, args, result) must hash the same so generic_repeat fires.
        a = _hash_tool_call("t", {"q": "x"}, _result_signature({"ok": True}))
        b = _hash_tool_call("t", {"q": "x"}, _result_signature({"ok": True}))
        self.assertEqual(a, b)

    def test_volatile_fields_filtered_so_polling_differs_from_loop(self):
        # Two polls that differ ONLY in a volatile field share a signature
        # (treated as the same -> loop), while a real value change differs.
        s1 = _result_signature({"value": 1, "ts": 100})
        s2 = _result_signature({"value": 1, "ts": 200})
        s3 = _result_signature({"value": 2, "ts": 300})
        self.assertEqual(s1, s2, "ts is volatile -> same signature")
        self.assertNotEqual(s1, s3, "value changed -> different signature")


if __name__ == "__main__":
    unittest.main()
