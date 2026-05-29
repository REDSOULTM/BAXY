"""Safety hook intercepts checkout-pattern URLs and paid actions.

Hotfix I 2026-05-17. Structural detection — operates on args
(URL, action), never on user/LLM text.
"""
from __future__ import annotations

import unittest
from unittest import mock

import gemma4_agent.safety_pkg.safety_hook as sh
from gemma4_agent.safety_pkg.safety_hook import evaluate_tool_call


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


class CheckoutWindowClickGuardTest(unittest.TestCase):
    """HUECO CERRADO 2026-05-26: un click GENÉRICO en una pantalla de checkout
    (gui.click_button 'Comprar' en Steam) ya no se cuela. Decisión: si la
    ventana al frente es una tienda/checkout, CUALQUIER click pide confirmación
    — la señal del SO manda; el label del botón no decide (frágil). Mockeamos
    _foreground_is_checkout para no depender de la ventana real."""

    def test_click_button_on_checkout_window_is_blocked(self):
        with mock.patch.object(sh, "_foreground_is_checkout", return_value=True):
            v = evaluate_tool_call(
                "gui", "click_button", {"action": "click_button", "label": "Comprar"})
        self.assertTrue(v["block"])
        self.assertEqual(v["pattern"], "gui_click_on_checkout_window")

    def test_computer_use_goal_on_checkout_window_is_blocked(self):
        with mock.patch.object(sh, "_foreground_is_checkout", return_value=True):
            v = evaluate_tool_call(
                "computer_use", "", {"goal": "comprar el juego"})
        self.assertTrue(v["block"])

    def test_click_without_checkout_window_passes(self):
        # Click idéntico pero NO en un checkout -> navegación normal, no bloquea.
        with mock.patch.object(sh, "_foreground_is_checkout", return_value=False):
            v = evaluate_tool_call(
                "gui", "click_button", {"action": "click_button", "label": "Comprar"})
        self.assertFalse(v["block"])

    def test_non_click_on_checkout_window_passes(self):
        # type/scroll/etc no avanza un pago por sí mismo -> no bloquea (el click
        # de confirmación sí lo hará). Evita bloquear todo el flujo de checkout.
        with mock.patch.object(sh, "_foreground_is_checkout", return_value=True):
            v = evaluate_tool_call(
                "gui", "type", {"action": "type", "text": "datos"})
        self.assertFalse(v["block"])

    def test_foreground_is_checkout_reads_window_title(self):
        # Verifica la señal del SO: estado de pago/checkout -> True.
        with mock.patch("gemma4_agent.computer_use._foreground_title",
                        return_value="Steam Checkout"):
            self.assertTrue(sh._foreground_is_checkout())
        with mock.patch("gemma4_agent.computer_use._foreground_title",
                        return_value="Resident Evil — Steam"):
            self.assertFalse(sh._foreground_is_checkout())
        with mock.patch("gemma4_agent.computer_use._foreground_title",
                        return_value="Bloc de notas"):
            self.assertFalse(sh._foreground_is_checkout())

    def test_foreground_read_failure_is_safe_false(self):
        # Si no se puede leer el título, NO bloquea de más (fallback seguro).
        with mock.patch("gemma4_agent.computer_use._foreground_title",
                        side_effect=RuntimeError("no win32")):
            self.assertFalse(sh._foreground_is_checkout())


if __name__ == "__main__":
    unittest.main()
