"""Regression test for the streaming-hang bug observed 2026-05-16 19:48.

Symptom: `media play disney` hung indefinitely (truncated by 60s tool
watchdog). Root cause: `browser_real_tool` called `_tabs(session)` after
CDP attach, which calls `page.title()` on every Opera tab. `page.title()`
is a sync CDP roundtrip that blocks on pages with long-lived event streams
(claude.ai SSE, gmail websocket, GX Corner service-workers). With ~14
targets in Opera, the cumulative block could exceed 60s.

Fixes:
  1. `_tabs(session)`: stopped calling `page.title()` — `page.url` (cached
     attribute) is enough to identify a tab.
  2. `browser_real_tool` action="connect_cdp": stopped auto-enumerating
     tabs at attach time (`tabs=[]` returned; caller can request tabs
     explicitly via action="tabs" if needed).
"""
from __future__ import annotations

import inspect
import unittest


class TestTabsAvoidsTitleCall(unittest.TestCase):
    """`_tabs()` MUST NOT call page.title() — it can block 10+ seconds
    per page on tabs with active CDP message streams.
    """

    @staticmethod
    def _strip_comments(src: str) -> str:
        # Drop Python line comments so we test actual code, not warnings.
        out = []
        for line in src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            # Drop inline comments too (split on first # not inside quotes —
            # naive but sufficient for the codebase here).
            if "#" in line:
                in_str = False
                quote = ""
                cut = len(line)
                i = 0
                while i < len(line):
                    c = line[i]
                    if c in ("'", '"') and (i == 0 or line[i - 1] != "\\"):
                        if not in_str:
                            in_str = True
                            quote = c
                        elif quote == c:
                            in_str = False
                    elif c == "#" and not in_str:
                        cut = i
                        break
                    i += 1
                line = line[:cut]
            out.append(line)
        return "\n".join(out)

    def test_tabs_does_not_call_page_title(self):
        from gemma4_agent import ops_tools
        src = self._strip_comments(inspect.getsource(ops_tools._tabs))
        self.assertNotIn(
            "page.title(", src,
            "_tabs() must NOT call page.title() — it blocks on SSE/WS pages",
        )

    def test_page_result_does_not_call_page_title(self):
        from gemma4_agent import ops_tools
        src = self._strip_comments(inspect.getsource(ops_tools._page_result))
        self.assertNotIn(
            "page.title(", src,
            "_page_result() must NOT call page.title() — same reason as _tabs()",
        )

    def test_connect_cdp_does_not_enumerate_tabs(self):
        """The action="connect_cdp" branch must return tabs=[] instead of
        calling _tabs(session). Tabs can be enumerated explicitly later
        if a caller really needs them."""
        from gemma4_agent import ops_tools
        src = inspect.getsource(ops_tools.browser_real_tool)
        # Find the connect_cdp block.
        idx = src.find('action == "connect_cdp"')
        self.assertGreater(idx, 0, "connect_cdp branch missing")
        # Within the next ~600 chars, look for the return statement.
        snippet = src[idx:idx + 800]
        # The fix returns "tabs=[]" (empty list) literally; the old code
        # returned "tabs=_tabs(session)".
        self.assertIn("tabs=[]", snippet,
                      "connect_cdp must return tabs=[] (lazy enumeration)")
        self.assertNotIn("tabs=_tabs(session)", snippet,
                          "connect_cdp must NOT eagerly call _tabs(session)")


if __name__ == "__main__":
    unittest.main()
