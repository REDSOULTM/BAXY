"""Safety hook intercepts checkout-pattern URLs and paid actions.

Hotfix I 2026-05-17. Structural detection — operates on args
(URL, action), never on user/LLM text.
"""
from __future__ import annotations

import unittest

from gemma4_agent.safety_hook import evaluate_tool_call


class SafetyHookTest(unittest.TestCase):
    def test_steam_checkout_url_is_blocked(self) -> None:
        v = evaluate_tool_call(
            "browser", "open",
            {"url": "https://store.steampowered.com/checkout/?cart=123"},
        )
        self.assertTrue(v["block"])
        self.assertIn("checkout", v["reason"].lower())

    def test_paypal_checkout_is_blocked(self) -> None:
        v = evaluate_tool_call(
            "browser_real", "goto",
            {"url": "https://www.paypal.com/checkoutnow?token=abc"},
        )
        self.assertTrue(v["block"])

    def test_stripe_checkout_is_blocked(self) -> None:
        v = evaluate_tool_call(
            "browser", "open",
            {"url": "https://checkout.stripe.com/c/pay/cs_test_abc"},
        )
        self.assertTrue(v["block"])

    def test_amazon_buy_us_is_blocked(self) -> None:
        v = evaluate_tool_call(
            "browser", "open",
            {"url": "https://www.amazon.com/gp/buy/spc/handlers/display.html"},
        )
        self.assertTrue(v["block"])

    def test_amazon_buy_intl_is_blocked(self) -> None:
        # Cross-region Amazon: amazon.co.uk/gp/buy must also match.
        v = evaluate_tool_call(
            "browser", "open",
            {"url": "https://www.amazon.co.uk/gp/buy/spc"},
        )
        self.assertTrue(v["block"])

    def test_steam_purchase_action_is_blocked(self) -> None:
        v = evaluate_tool_call(
            "steam", "purchase",
            {"app_id": 730},
        )
        self.assertTrue(v["block"])
        self.assertIn("paid action", v["reason"].lower())

    def test_steam_buy_action_is_blocked(self) -> None:
        v = evaluate_tool_call("steam", "buy", {"app_id": 570})
        self.assertTrue(v["block"])

    def test_game_launcher_purchase_is_blocked(self) -> None:
        v = evaluate_tool_call(
            "game_launcher", "purchase", {"game": "Cyberpunk"},
        )
        self.assertTrue(v["block"])

    def test_safe_steam_app_page_passes(self) -> None:
        # The app PAGE is fine — only the checkout path is blocked.
        v = evaluate_tool_call(
            "browser", "open",
            {"url": "https://store.steampowered.com/app/730/CSGO/"},
        )
        self.assertFalse(v["block"])

    def test_no_url_no_paid_action_passes(self) -> None:
        v = evaluate_tool_call(
            "filesystem", "list",
            {"path": "C:\\Users"},
        )
        self.assertFalse(v["block"])

    def test_safe_non_checkout_url_passes(self) -> None:
        v = evaluate_tool_call(
            "browser", "open",
            {"url": "https://github.com/anthropic/claude-code"},
        )
        self.assertFalse(v["block"])

    def test_href_arg_also_inspected(self) -> None:
        # Some tools use 'href' instead of 'url'.
        v = evaluate_tool_call(
            "browser_real", "click",
            {"href": "https://www.paypal.com/checkoutnow"},
        )
        self.assertTrue(v["block"])

    def test_block_response_includes_pattern_id(self) -> None:
        # Pattern field lets operators bucket trace events.
        v = evaluate_tool_call(
            "browser", "open",
            {"url": "https://checkout.stripe.com/x"},
        )
        self.assertTrue(v["block"])
        self.assertIn("pattern", v)
        self.assertIn("stripe", v["pattern"])


if __name__ == "__main__":
    unittest.main()
