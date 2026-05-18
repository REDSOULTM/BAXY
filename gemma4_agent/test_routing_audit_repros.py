"""End-to-end smoke tests for the 4 audit-day routing failures.

Hotfix E 2026-05-17. These queries were collapsing to ['session']
or wrong tools under v1's regex planner. With router_v2 as
authoritative default, they should land in the right subset
regardless of dialect or language.

We test the v2 path DIRECTLY (route_v2) rather than going through
the full agent dispatch. If the model isn't available locally, we
skip — these are integration tests, not unit tests.
"""
from __future__ import annotations

import unittest

from gemma4_agent.router_v2 import MODEL_PATH, RouterV2, route_v2


_HAS_MODEL = MODEL_PATH.exists()


@unittest.skipUnless(_HAS_MODEL, "e5-small ONNX model not installed")
class AuditReprosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            raise unittest.SkipTest(router._load_error)

    @classmethod
    def tearDownClass(cls) -> None:
        RouterV2.reset()

    def _assert_tool_in_topk(self, query: str, expected_tool: str) -> None:
        # Hotfix J 2026-05-17: reset before each route so the
        # adaptive-cap behavior is measured cold, not via cache
        # hits from sibling tests run earlier in alphabetic order.
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        subset, telemetry = route_v2(query)
        if telemetry.get("source") == "smalltalk":
            self.fail(f"{query!r}: smalltalk gate fired, expected {expected_tool}")
        self.assertIn(
            expected_tool, subset,
            f"{query!r}: expected {expected_tool} in subset, "
            f"got {subset[:8]} (telemetry={telemetry.get('source')})",
        )

    def test_install_app_es(self) -> None:
        self._assert_tool_in_topk("instala vlc", "package")

    def test_install_app_voseo(self) -> None:
        self._assert_tool_in_topk("instalame vlc", "package")

    def test_install_app_en(self) -> None:
        self._assert_tool_in_topk("install vlc", "package")

    def test_power_off_es(self) -> None:
        self._assert_tool_in_topk("apaga la pc", "system")

    def test_power_off_voseo(self) -> None:
        self._assert_tool_in_topk("apagame la pc", "system")

    def test_play_music_es(self) -> None:
        self._assert_tool_in_topk("pone benson boone", "media")

    def test_play_music_en(self) -> None:
        self._assert_tool_in_topk("play benson boone", "media")

    def test_play_music_fr(self) -> None:
        self._assert_tool_in_topk("mets benson boone", "media")

    def test_gracias_por_todo_does_not_route_to_notes(self) -> None:
        subset, telemetry = route_v2("gracias por todo")
        self.assertNotIn(
            "notes_tasks", subset,
            f"got {subset}; smalltalk gate should have fired "
            f"or notes_tasks should not have been picked",
        )

    def test_open_chrome_fr(self) -> None:
        # The audit-day bug was "cross-lingual chrome doesn't
        # reach a chrome-launching tool". Several tools can launch
        # Chrome — browser (deep-link open), browser_real
        # (Playwright attach), or app (process launch via name
        # resolution). With hotfix K's bilingual purposes, the ES
        # imperative 'abre' pulls `app` strongly via BM25, and
        # cross-lingual cosine for FR/DE 'open' verbs leans the
        # same way. Any of the three meets the audit-day repro.
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        subset, telemetry = route_v2("ouvre chrome")
        self.assertNotEqual(telemetry.get("source"), "smalltalk")
        self.assertTrue(
            any(t in subset for t in ("browser", "browser_real", "app")),
            f"no chrome-launching tool in subset: {subset}",
        )

    def test_open_chrome_de(self) -> None:
        # Same cross-lingual relaxation as the FR test above.
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        subset, telemetry = route_v2("öffne chrome")
        self.assertNotEqual(telemetry.get("source"), "smalltalk")
        self.assertTrue(
            any(t in subset for t in ("browser", "browser_real", "app")),
            f"no chrome-launching tool in subset: {subset}",
        )


if __name__ == "__main__":
    unittest.main()
