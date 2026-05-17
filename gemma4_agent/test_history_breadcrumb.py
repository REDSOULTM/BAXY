"""Regression test for the breadcrumb pre-pass added to history
compaction (hotfix C, 2026-05-17).

Bug repro: office.create_presentation returned
path="C:\\...\\file.pptx", LLM replied "en la ruta especificada"
without including the path, and the next turn asked "where is it?"
but the LLM had no way to recover the path because
_compact_completed_history drops tool messages entirely.

The fix stitches locator-keys (path, url, selected_title,
image_path, deeplink) from each tool_result onto the assistant
reply of the SAME turn as a discreet `[breadcrumb: ...]` suffix,
BEFORE the drop runs. Idempotent: if the locator was already
mentioned verbatim by the LLM, nothing is added.

The breadcrumb stitcher is exposed as a pure function in
``gemma4_agent.agent_compaction`` so this test can exercise it
without spinning up a full AgentRunner (which has a heavy
__init__).
"""
from __future__ import annotations

import json
import unittest

from gemma4_agent.agent_compaction import stitch_breadcrumbs


class BreadcrumbStitchTest(unittest.TestCase):
    def test_path_stitched_onto_assistant_reply_when_missing(self) -> None:
        path = r"C:\Users\me\Desktop\report.pptx"
        hist = [
            {"role": "user", "content": "Hazme un powerpoint"},
            {"role": "assistant", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "office", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_1",
             "content": json.dumps({"ok": True, "path": path, "kind": "presentation"})},
            {"role": "assistant", "content": "Listo, creé el PowerPoint en la ruta especificada."},
        ]
        out = stitch_breadcrumbs(hist)
        final = out[-1]
        self.assertEqual(final["role"], "assistant")
        self.assertIn(path, str(final["content"]),
                      f"path should have been stitched: {final['content']!r}")
        self.assertIn("[breadcrumb:", str(final["content"]))

    def test_path_NOT_duplicated_when_already_cited(self) -> None:
        path = r"C:\Users\me\Desktop\report.pptx"
        hist = [
            {"role": "user", "content": "Hazme un powerpoint"},
            {"role": "assistant", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "office", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_1",
             "content": json.dumps({"ok": True, "path": path})},
            {"role": "assistant", "content": f"Listo, lo guardé en {path}."},
        ]
        out = stitch_breadcrumbs(hist)
        final_text = str(out[-1]["content"])
        # Locator appears exactly once (not duplicated by breadcrumb).
        self.assertEqual(final_text.count(path), 1,
                         f"path duplicated: {final_text!r}")
        self.assertNotIn("[breadcrumb:", final_text)

    def test_url_locator_stitched(self) -> None:
        url = "https://www.youtube.com/watch?v=abc123"
        hist = [
            {"role": "user", "content": "pon un video"},
            {"role": "assistant", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "media", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_1",
             "content": json.dumps({"ok": True, "url": url})},
            {"role": "assistant", "content": "Listo, video abierto."},
        ]
        out = stitch_breadcrumbs(hist)
        final_text = str(out[-1]["content"])
        self.assertIn(url, final_text)
        self.assertIn("url=", final_text)

    def test_no_op_when_no_tool_messages(self) -> None:
        hist = [
            {"role": "user", "content": "hola"},
            {"role": "assistant", "content": "hola, ¿en qué te ayudo?"},
        ]
        out = stitch_breadcrumbs(hist)
        final = next(m for m in out if m.get("role") == "assistant")
        self.assertNotIn("[breadcrumb:", str(final["content"]))
        # Pure no-op should preserve content byte-for-byte.
        self.assertEqual(final["content"], "hola, ¿en qué te ayudo?")

    def test_selected_title_locator_stitched(self) -> None:
        # Coverage for a non-path / non-url locator key.
        title = "Daredevil S01E01"
        hist = [
            {"role": "user", "content": "pone daredevil en netflix"},
            {"role": "assistant", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "media", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_1",
             "content": json.dumps({"ok": True, "selected_title": title})},
            {"role": "assistant", "content": "Listo, lo puse."},
        ]
        out = stitch_breadcrumbs(hist)
        final_text = str(out[-1]["content"])
        self.assertIn(title, final_text)


if __name__ == "__main__":
    unittest.main()
