"""Tests for inventory + app discovery integration."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from gemma4_agent.voice import inventory
from gemma4_agent.voice.inventory import (
    STATIC_INVENTORY, build_initial_prompt, get_inventory,
)


class GetInventoryTest(unittest.TestCase):
    def setUp(self):
        # Reset module-level discovery cache between tests.
        inventory._DISCOVERY_CACHE = None

    def test_get_inventory_without_discovery_is_static_plus_user(self):
        # include_discovery=False = deterministic test path.
        inv = get_inventory(include_discovery=False)
        for cat in ("apps", "verbs", "wake_words"):
            self.assertIn(cat, inv)
        # Apps come ONLY from STATIC + user overrides; no Get-StartApps
        # output expected.
        self.assertGreaterEqual(len(inv["apps"]), len(STATIC_INVENTORY["apps"]))

    def test_discovery_extends_apps_category(self):
        fake_discovered = ["MyCoolApp", "AnotherApp", "Chrome"]  # Chrome dupes
        with patch.object(
            inventory, "_discover_installed_apps", return_value=fake_discovered,
        ):
            inv = get_inventory(include_discovery=True)
        self.assertIn("MyCoolApp", inv["apps"])
        self.assertIn("AnotherApp", inv["apps"])
        # Chrome should not be duplicated (case-insensitive dedupe).
        chrome_count = sum(
            1 for x in inv["apps"] if x.lower() == "chrome"
        )
        self.assertEqual(chrome_count, 1)

    def test_discovery_failure_falls_back_to_static(self):
        with patch.object(
            inventory, "_discover_installed_apps", side_effect=RuntimeError("nope"),
        ):
            # get_inventory itself catches via the cache layer, BUT the
            # current implementation lets the exception bubble. Verify
            # the wrapper handles it.
            try:
                inv = get_inventory(include_discovery=True)
                # If we got here, the wrapper handled the exception.
                self.assertIn("apps", inv)
            except RuntimeError:
                # If it raises, the wrapper isn't catching — that's a
                # design choice we can flag here for fix.
                self.fail(
                    "get_inventory should catch discovery exceptions; "
                    "wrap _discover_installed_apps in try/except."
                )


class BuildInitialPromptTest(unittest.TestCase):
    def setUp(self):
        inventory._DISCOVERY_CACHE = None

    def test_prompt_contains_bilingual_wake_seed(self):
        prompt = build_initial_prompt()
        self.assertIn("Hey Gemma", prompt)
        self.assertIn("abre Chrome", prompt)
        self.assertIn("open Chrome", prompt)

    def test_prompt_caps_under_900_chars(self):
        # Sanity: the prompt fits under Whisper's 224-token budget
        # (conservative ~880 chars).
        prompt = build_initial_prompt()
        self.assertLessEqual(len(prompt), 900)

    def test_prompt_caps_even_with_huge_discovery(self):
        # 100 random app names should not blow the cap.
        many_apps = [f"App{i}" for i in range(100)]
        with patch.object(
            inventory, "_discover_installed_apps", return_value=many_apps,
        ):
            inv = get_inventory(include_discovery=True)
            prompt = build_initial_prompt(inv)
        self.assertLessEqual(len(prompt), 900)


class AppDiscoverySafetyTest(unittest.TestCase):
    """The discovery module must never crash the voice pipeline."""

    def test_discover_apps_returns_list_on_any_platform(self):
        from gemma4_agent.voice.app_discovery import discover_apps
        result = discover_apps()
        # Just verify it returns a list — content depends on OS.
        self.assertIsInstance(result, list)
        # If non-empty, all entries must be strings.
        for entry in result:
            self.assertIsInstance(entry, str)


if __name__ == "__main__":
    unittest.main()
