"""Breadcrumbs accumulate over repeated compactions. Keep only the
most recent one per assistant message to avoid context inflation.

Hotfix H 2026-05-17.
"""
from __future__ import annotations

import unittest

from gemma4_agent.agent_core.agent_compaction import compact_history_content


class BreadcrumbCompactionTest(unittest.TestCase):
    def test_single_breadcrumb_preserved(self) -> None:
        text = "Listo, abrí spotify.\n[breadcrumb: url=https://spotify.com/track/abc]"
        out = compact_history_content(text)
        self.assertIn("url=https://spotify.com/track/abc", out)
        self.assertNotIn("collapsed", out)

    def test_multiple_breadcrumbs_collapsed(self) -> None:
        text = (
            "Listo.\n"
            "[breadcrumb: path=C:\\a.pptx]\n"
            "[breadcrumb: path=C:\\b.pptx]\n"
            "[breadcrumb: url=https://example.com/latest]"
        )
        out = compact_history_content(text)
        self.assertIn("url=https://example.com/latest", out)
        self.assertIn("collapsed", out)
        self.assertNotIn("a.pptx", out)
        self.assertNotIn("b.pptx", out)

    def test_no_breadcrumb_is_no_op(self) -> None:
        text = "Listo, hecho."
        out = compact_history_content(text)
        self.assertEqual(out.strip(), "Listo, hecho.")

    def test_two_breadcrumbs_keep_second(self) -> None:
        text = (
            "Listo.\n"
            "[breadcrumb: path=C:\\first.pptx]\n"
            "[breadcrumb: path=C:\\second.pptx]"
        )
        out = compact_history_content(text)
        self.assertIn("second.pptx", out)
        self.assertIn("collapsed", out)
        self.assertNotIn("first.pptx", out)

    def test_list_content_breadcrumbs_collapsed(self) -> None:
        # When content is a list of multimodal items, the joined
        # text path should also collapse stacked breadcrumbs.
        content = [
            {"type": "text", "text": "Listo.\n[breadcrumb: path=C:\\a.pptx]"},
            {"type": "text", "text": "[breadcrumb: path=C:\\b.pptx]"},
            {"type": "text", "text": "[breadcrumb: url=https://x.com/latest]"},
        ]
        out = compact_history_content(content)
        self.assertIn("https://x.com/latest", out)
        self.assertIn("collapsed", out)
        self.assertNotIn("a.pptx", out)


if __name__ == "__main__":
    unittest.main()
