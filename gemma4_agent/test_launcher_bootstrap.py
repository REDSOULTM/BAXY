"""The launcher's start() command must call the router_v2 bootstrap
helper exactly once when the model is missing, and skip when it's
already present.

Hotfix E 2026-05-17.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch


class LauncherBootstrapTest(unittest.TestCase):
    def test_bootstrap_skipped_when_model_present(self) -> None:
        from gemma4_agent.launcher import _ensure_router_v2_model
        with patch("gemma4_agent.router_v2.MODEL_PATH") as mock_path:
            mock_path.exists.return_value = True
            with patch("scripts.bootstrap_e5_small.main") as mock_main:
                _ensure_router_v2_model()
                mock_main.assert_not_called()

    def test_bootstrap_invoked_when_model_absent(self) -> None:
        from gemma4_agent.launcher import _ensure_router_v2_model
        with patch("gemma4_agent.router_v2.MODEL_PATH") as mock_path:
            mock_path.exists.return_value = False
            with patch("scripts.bootstrap_e5_small.main") as mock_main:
                mock_main.return_value = 0
                _ensure_router_v2_model()
                mock_main.assert_called_once()

    def test_bootstrap_failure_does_not_raise(self) -> None:
        from gemma4_agent.launcher import _ensure_router_v2_model
        with patch("gemma4_agent.router_v2.MODEL_PATH") as mock_path:
            mock_path.exists.return_value = False
            with patch("scripts.bootstrap_e5_small.main",
                       side_effect=RuntimeError("network")):
                _ensure_router_v2_model()


if __name__ == "__main__":
    unittest.main()
