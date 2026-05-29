"""B9: cliente MCP — tests del skeleton (gate, config, fallback) con el SDK async
MOCKEADO (sin servidor real). La validación con un servidor MCP real (npx) es en vivo."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ..tools_pkg import mcp_client as M


class _EnvBase(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("GEMMA4_MCP")
        M.reset_cache()

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("GEMMA4_MCP", None)
        else:
            os.environ["GEMMA4_MCP"] = self._prev
        M.reset_cache()

    def _on(self):
        os.environ["GEMMA4_MCP"] = "1"

    def _off(self):
        os.environ["GEMMA4_MCP"] = "0"


class TestGate(_EnvBase):
    def test_default_off(self):
        os.environ.pop("GEMMA4_MCP", None)
        self.assertFalse(M.mcp_enabled())

    def test_on(self):
        self._on()
        self.assertTrue(M.mcp_enabled())


class TestConfig(_EnvBase):
    def test_missing_file(self):
        with mock.patch.object(M, "_CONFIG_PATH", Path(tempfile.gettempdir()) / "_no_mcp.json"):
            self.assertEqual(M._load_config(), [])

    def test_valid(self):
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text(json.dumps({"servers": [
            {"name": "fs", "command": "npx", "args": ["-y", "srv"]},
            {"name": "bad"},  # sin command -> filtrado
        ]}), encoding="utf-8")
        with mock.patch.object(M, "_CONFIG_PATH", tmp):
            cfg = M._load_config()
        self.assertEqual(len(cfg), 1)
        self.assertEqual(cfg[0]["name"], "fs")

    def test_invalid_json(self):
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text("{ not json", encoding="utf-8")
        with mock.patch.object(M, "_CONFIG_PATH", tmp):
            self.assertEqual(M._load_config(), [])


class TestDiscoverCall(_EnvBase):
    def test_discover_gate_off(self):
        self._off()
        self.assertEqual(M.discover_mcp_tools(force=True), [])

    def test_call_gate_off(self):
        self._off()
        r = M.call_mcp_tool("fs", "read_file")
        self.assertFalse(r["ok"])
        self.assertIn("disabled", r["error"].lower())

    def test_call_unknown_server(self):
        self._on()
        with mock.patch.object(M, "_load_config", return_value=[]):
            r = M.call_mcp_tool("nope", "read_file")
        self.assertFalse(r["ok"])
        self.assertIn("unknown", r["error"].lower())

    def test_discover_mocked(self):
        self._on()
        with mock.patch.object(M, "_load_config",
                               return_value=[{"name": "fs", "command": "npx", "args": []}]), \
             mock.patch.object(M, "_run_async",
                               return_value=[{"server": "fs", "name": "read_file",
                                              "description": "Read a file", "schema": {}}]):
            tools = M.discover_mcp_tools(force=True)
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "read_file")
        self.assertEqual(tools[0]["server"], "fs")

    def test_discover_swallows_server_error(self):
        self._on()
        with mock.patch.object(M, "_load_config",
                               return_value=[{"name": "fs", "command": "npx", "args": []}]), \
             mock.patch.object(M, "_run_async", side_effect=RuntimeError("boom")):
            tools = M.discover_mcp_tools(force=True)
        self.assertEqual(tools, [])  # error de un server no rompe el descubrimiento

    def test_call_mocked_ok(self):
        self._on()
        with mock.patch.object(M, "_load_config",
                               return_value=[{"name": "fs", "command": "npx", "args": []}]), \
             mock.patch.object(M, "_run_async",
                               return_value={"ok": True, "content": "hello", "is_error": False}):
            r = M.call_mcp_tool("fs", "read_file", {"path": "x"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["content"], "hello")

    def test_call_swallows_exception(self):
        self._on()
        with mock.patch.object(M, "_load_config",
                               return_value=[{"name": "fs", "command": "npx", "args": []}]), \
             mock.patch.object(M, "_run_async", side_effect=TimeoutError("slow")):
            r = M.call_mcp_tool("fs", "read_file", {"path": "x"})
        self.assertFalse(r["ok"])
        self.assertFalse(r.get("verified", True))


if __name__ == "__main__":
    unittest.main()
