"""Coverage gap (Fase 3): LlamaServerManager.start() has lifecycle/recovery
branches that protect a USER's manually-started server — never covered by a
test. These are fiabilidad-critical: the round-11 atexit teardown relies on
_external_detected being set so it NEVER kills a server the user ran by hand.

EJE del norte rector: FIABILIDAD. Pin: (1) standby profile doesn't start,
(2) an external server on :8080 is detected and NOT taken over, (3) a context
mismatch surfaces a warning, a >= context stays silent, (4) once external,
current_profile() is None and stop() is a no-op (atexit won't touch it)."""
from __future__ import annotations

import unittest
from unittest import mock

from gemma4_agent.infra.llama_server import LlamaServerManager
from gemma4_agent.infra.profiles import PROFILES


class TestStandbyBranch(unittest.TestCase):
    def test_standby_profile_does_not_start(self):
        mgr = LlamaServerManager()
        standby = PROFILES["standby"]
        self.assertFalse(standby.server_running, "fixture sanity: standby has server off")
        self.assertEqual(mgr.start(standby), "skipped_standby")


class TestExternalDetection(unittest.TestCase):
    def setUp(self):
        self.mgr = LlamaServerManager()
        self.profile = PROFILES["vram4"]  # único perfil (era vram8)

    def test_external_server_is_detected_not_taken_over(self):
        with mock.patch("gemma4_agent.llama_server.port_in_use", return_value=True), \
                mock.patch("gemma4_agent.llama_server.get_external_server_context",
                           return_value=None), \
                mock.patch("gemma4_agent.llama_server.subprocess.Popen") as popen:
            result = self.mgr.start(self.profile)
        self.assertEqual(result, "external")
        self.assertTrue(self.mgr.is_external_server())
        popen.assert_not_called()  # NEVER spawn over an external server

    def test_external_with_smaller_context_warns(self):
        with mock.patch("gemma4_agent.llama_server.port_in_use", return_value=True), \
                mock.patch("gemma4_agent.llama_server.get_external_server_context",
                           return_value=2048):  # < vram8's context_size
            self.mgr.start(self.profile)
        msg = self.mgr.external_context_mismatch_msg()
        self.assertIsNotNone(msg)
        self.assertIn("2048", msg)

    def test_external_with_larger_context_is_silent(self):
        big = int(self.profile.context_size) + 100000
        with mock.patch("gemma4_agent.llama_server.port_in_use", return_value=True), \
                mock.patch("gemma4_agent.llama_server.get_external_server_context",
                           return_value=big):
            self.mgr.start(self.profile)
        # Server has >= capacity -> no warning (it just ignores the surplus).
        self.assertIsNone(self.mgr.external_context_mismatch_msg())

    def test_external_makes_current_profile_none_and_stop_noop(self):
        # This is the invariant the round-11 atexit relies on.
        with mock.patch("gemma4_agent.llama_server.port_in_use", return_value=True), \
                mock.patch("gemma4_agent.llama_server.get_external_server_context",
                           return_value=None):
            self.mgr.start(self.profile)
        self.assertIsNone(self.mgr.current_profile(),
                          "an external server's profile is unknown to us")
        # stop() must NOT claim to have killed anything (it's not ours).
        self.assertFalse(self.mgr.stop(), "stop() must no-op on an external server")


if __name__ == "__main__":
    unittest.main()
