"""ProfileWatcher must RESTART llama-server on an auto-switch, not just set env
vars — otherwise an auto-downgrade (game launched -> free VRAM) is cosmetic: the
old/bigger model stays resident in GPU. Mirrors the PUT /profile behavior.

Mocks the shared manager so no real server/GPU is touched."""
from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import patch

from gemma4_agent import profile_watcher as pw
from gemma4_agent.profiles import PROFILES, get_active_profile, set_active_profile


class _FakeMgr:
    def __init__(self):
        self.restarts = []

    def force_restart_for_profile(self, profile, *a, **k):
        self.restarts.append(profile.name)
        return "started"


class TestWatcherRestart(unittest.TestCase):
    def setUp(self):
        self._saved = get_active_profile().name

    def tearDown(self):
        try:
            set_active_profile(self._saved)
        except Exception:
            pass

    def _make_watcher(self):
        cfg = pw.WatcherConfig(enabled=True, downgrade_to="vram4", restore_to="vram8")
        return pw.ProfileWatcher(cfg)

    def _switch_and_wait(self, watcher, target, fake):
        watcher._switch_to(target, "test")
        # restart runs in a daemon thread; wait briefly for it to record.
        for _ in range(50):
            if fake.restarts:
                break
            time.sleep(0.02)

    def test_switch_to_different_model_restarts_server(self):
        # vram8 (E4B-Q4) -> vram4 (E4B-Q4) share a model; pick two that DIFFER.
        # vram8 model != vram12 model (E4B-Q4 vs E4B-Q6) -> restart expected.
        set_active_profile("vram8")
        fake = _FakeMgr()
        w = self._make_watcher()
        with patch("gemma4_agent.llama_server.get_shared_manager", return_value=fake):
            self._switch_and_wait(w, "vram12", fake)
        self.assertEqual(fake.restarts, ["vram12"],
                         "a model change must trigger a server restart")

    def test_switch_to_same_profile_no_restart(self):
        set_active_profile("vram8")
        fake = _FakeMgr()
        w = self._make_watcher()
        with patch("gemma4_agent.llama_server.get_shared_manager", return_value=fake):
            # switch to the SAME profile -> no binary-affecting change.
            w._switch_to("vram8", "test")
            time.sleep(0.3)
        self.assertEqual(fake.restarts, [],
                         "switching to the same profile must not restart")

    def test_restart_failure_does_not_crash_switch(self):
        set_active_profile("vram8")

        def _boom(*a, **k):
            raise RuntimeError("manager unavailable")

        w = self._make_watcher()
        with patch("gemma4_agent.llama_server.get_shared_manager", side_effect=_boom):
            # Must not raise even though the manager blows up.
            w._switch_to("vram12", "test")
            time.sleep(0.3)
        self.assertEqual(get_active_profile().name, "vram12",
                         "profile still switches even if the restart fails")


if __name__ == "__main__":
    unittest.main()
