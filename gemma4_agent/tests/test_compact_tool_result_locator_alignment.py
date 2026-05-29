"""compact_tool_result.core_keys must include every key in
_LOCATOR_KEYS so locators survive both compaction (when payload
exceeds TOOL_RESULT_LIMIT) and the breadcrumb pre-pass.

Hotfix F 2026-05-17.
"""
from __future__ import annotations

import unittest

from gemma4_agent.agent_core.agent_compaction import (
    _LOCATOR_KEYS,
    compact_tool_result,
)


class LocatorAlignmentTest(unittest.TestCase):
    def test_compact_preserves_each_locator_key_when_oversized(self) -> None:
        big_payload: dict = {
            "junk": "x" * 5000,
            "path": "C:\\file.pptx",
            "url": "https://example.com/path",
            "selected_title": "Daredevil",
            "image_path": "C:\\screenshot.png",
            "deeplink": "spotify:track:abc",
        }
        out = compact_tool_result("tool", {}, big_payload)
        for k in _LOCATOR_KEYS:
            self.assertIn(
                k, out,
                f"{k} dropped during compaction; got keys: {list(out.keys())}",
            )
            self.assertEqual(
                out[k], big_payload[k],
                f"{k} value changed during compaction",
            )

    def test_deeplink_specifically_survives_oversized_payload(self) -> None:
        # The audit-day bug: a streaming tool returning a 5KB+
        # payload with deeplink lost the deeplink at compaction.
        big_payload = {
            "junk_a": "y" * 3000,
            "junk_b": "z" * 3000,
            "deeplink": "spotify:track:7CkB6QF6PKp0E1nF1bM2lE",
            "ok": True,
        }
        out = compact_tool_result("media", {"action": "play"}, big_payload)
        self.assertIn("deeplink", out)
        self.assertEqual(out["deeplink"], big_payload["deeplink"])

    def test_small_payload_passes_through_unchanged(self) -> None:
        # Payloads under TOOL_RESULT_LIMIT should pass through the
        # compact_json shortcut, not the core_keys carve-out.
        small = {"ok": True, "deeplink": "spotify:track:x"}
        out = compact_tool_result("media", {}, small)
        self.assertIn("deeplink", out)


if __name__ == "__main__":
    unittest.main()
