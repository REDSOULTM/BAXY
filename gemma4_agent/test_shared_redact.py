"""redact_sensitive masks secret-looking keys for confirmation prompts and the
hard_gate safety path. It must NEVER raise — it's on a safety path. The
`v not in (None, "")` check raised ValueError on a numpy array value ("truth
value ambiguous"). These pin the behavior + the no-crash invariant."""
from __future__ import annotations

import unittest

from gemma4_agent._shared import redact_sensitive


class TestRedactSensitive(unittest.TestCase):
    def test_masks_sensitive_keys(self):
        out = redact_sensitive({"password": "secret", "api_key": "abc", "user": "ema"})
        self.assertEqual(out["password"], "***REDACTED***")
        self.assertEqual(out["api_key"], "***REDACTED***")
        self.assertEqual(out["user"], "ema")

    def test_keeps_absent_markers(self):
        # None / "" stay so logs distinguish "absent" from "redacted".
        out = redact_sensitive({"token": None, "secret": ""})
        self.assertIsNone(out["token"])
        self.assertEqual(out["secret"], "")

    def test_recurses_into_nested(self):
        out = redact_sensitive({"outer": {"password": "x"}, "list": [{"token": "y"}]})
        self.assertEqual(out["outer"]["password"], "***REDACTED***")
        self.assertEqual(out["list"][0]["token"], "***REDACTED***")

    def test_depth_cap_on_self_reference(self):
        d = {"a": 1}
        d["self"] = d  # cyclic
        # Must not RecursionError (depth cap at 6).
        redact_sensitive(d)

    def test_numpy_value_under_sensitive_key_does_not_raise(self):
        np = __import__("numpy")
        out = redact_sensitive({"password": np.array([1, 2, 3])})
        self.assertEqual(out["password"], "***REDACTED***")

    def test_non_dict_passthrough(self):
        self.assertEqual(redact_sensitive("plain"), "plain")
        self.assertEqual(redact_sensitive(42), 42)
        self.assertEqual(redact_sensitive(None), None)


if __name__ == "__main__":
    unittest.main()
