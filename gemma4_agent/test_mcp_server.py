"""Unit tests for MCP server (TIER 2 #7).

No spawn de proceso ni stdin loop — testeamos los handlers JSON-RPC en
memoria. Para tools/call usamos un tool read-only (system.time) que es
seguro de ejecutar en CI/dev.
"""
from __future__ import annotations

import json
import unittest

from .mcp_server import (
    MCP_PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    _build_tool_list,
    _handle_initialize,
    _handle_request,
    _handle_tools_call,
    _handle_tools_list,
)


class TestToolList(unittest.TestCase):
    """tools/list contract."""

    def test_build_tool_list_nonempty(self):
        tools = _build_tool_list()
        self.assertGreater(len(tools), 10, "expected many compound tools")

    def test_tool_shape(self):
        tools = _build_tool_list()
        for t in tools[:5]:
            self.assertIn("name", t)
            self.assertIn("description", t)
            self.assertIn("inputSchema", t)
            self.assertIsInstance(t["name"], str)
            self.assertGreater(len(t["name"]), 0)

    def test_includes_core_tools(self):
        names = {t["name"] for t in _build_tool_list()}
        for required in ("system", "app", "steam", "window", "gui",
                          "filesystem", "audio", "web", "memory", "verify"):
            self.assertIn(required, names, f"missing core tool: {required}")


class TestInitialize(unittest.TestCase):
    """initialize handshake."""

    def test_protocol_version(self):
        resp = _handle_initialize({})
        self.assertEqual(resp["protocolVersion"], MCP_PROTOCOL_VERSION)

    def test_server_info(self):
        resp = _handle_initialize({})
        info = resp["serverInfo"]
        self.assertEqual(info["name"], SERVER_NAME)
        self.assertEqual(info["version"], SERVER_VERSION)

    def test_capabilities(self):
        resp = _handle_initialize({})
        self.assertIn("tools", resp["capabilities"])


class TestJsonRpcDispatch(unittest.TestCase):
    """_handle_request dispatch wrapper."""

    def test_initialize_request(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        resp = _handle_request(req)
        self.assertEqual(resp["jsonrpc"], "2.0")
        self.assertEqual(resp["id"], 1)
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["protocolVersion"], MCP_PROTOCOL_VERSION)

    def test_tools_list_request(self):
        req = {"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}
        resp = _handle_request(req)
        self.assertEqual(resp["id"], 7)
        self.assertIn("tools", resp["result"])
        self.assertGreater(len(resp["result"]["tools"]), 10)

    def test_unknown_method(self):
        req = {"jsonrpc": "2.0", "id": 99, "method": "does/not/exist", "params": {}}
        resp = _handle_request(req)
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32601)

    def test_notification_no_response(self):
        # No `id` field -> notification. Server must NOT respond.
        req = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        resp = _handle_request(req)
        self.assertIsNone(resp)

    def test_notification_unknown_method_silent(self):
        # Unknown methods without id should also produce no response (notifications).
        req = {"jsonrpc": "2.0", "method": "unknown/notification", "params": {}}
        resp = _handle_request(req)
        self.assertIsNone(resp)


class TestToolsCall(unittest.TestCase):
    """tools/call dispatch — read-only tool only (system.time)."""

    def test_call_system_time(self):
        resp = _handle_tools_call({"name": "system", "arguments": {"action": "time"}})
        self.assertIn("content", resp)
        self.assertFalse(resp["isError"], f"call returned error: {resp}")
        # MCP content is list[{type, text}]
        self.assertEqual(resp["content"][0]["type"], "text")
        payload = json.loads(resp["content"][0]["text"])
        self.assertTrue(payload.get("ok"))
        self.assertIn("iso", payload)

    def test_call_unknown_tool(self):
        resp = _handle_tools_call({"name": "this_tool_does_not_exist", "arguments": {}})
        # tools.py returns dict with error; we mark isError=True
        self.assertTrue(resp["isError"])

    def test_call_via_request(self):
        # Full JSON-RPC round trip
        req = {
            "jsonrpc": "2.0", "id": 42,
            "method": "tools/call",
            "params": {"name": "system", "arguments": {"action": "time"}},
        }
        resp = _handle_request(req)
        self.assertEqual(resp["id"], 42)
        self.assertIn("result", resp)
        self.assertIn("content", resp["result"])


class TestRequestRobustness(unittest.TestCase):
    """Hardening: malformed-but-parseable JSON-RPC must not crash the handler."""

    def test_empty_request_dict(self):
        # {} has no method, no id — handler treats it as a notification of an
        # unknown method (silently dropped). Must not raise.
        resp = _handle_request({})
        self.assertIsNone(resp)

    def test_missing_method_with_id_returns_method_not_found(self):
        # id present but method missing -> -32601 (method "" is not found).
        req = {"jsonrpc": "2.0", "id": 5}
        resp = _handle_request(req)
        self.assertEqual(resp["id"], 5)
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32601)

    def test_string_params_does_not_crash(self):
        # Misbehaving client sends params=str instead of dict. Handler should
        # accept gracefully (initialize ignores params anyway).
        req = {"jsonrpc": "2.0", "id": 6, "method": "initialize", "params": "bogus"}
        resp = _handle_request(req)
        self.assertEqual(resp["id"], 6)
        # Either result or error — never an uncaught exception.
        self.assertTrue("result" in resp or "error" in resp)

    def test_tools_call_with_missing_arguments(self):
        # No `arguments` key — should be treated as {}.
        resp = _handle_tools_call({"name": "system"})
        self.assertIn("content", resp)
        # system with no action will return its own error; that's fine,
        # we only assert the handler didn't crash.

    def test_tools_call_with_none_arguments(self):
        resp = _handle_tools_call({"name": "system", "arguments": None})
        self.assertIn("content", resp)

    def test_tools_call_with_empty_name(self):
        # name="" -> registry returns "unknown tool" -> isError=True.
        resp = _handle_tools_call({"name": "", "arguments": {}})
        self.assertTrue(resp["isError"])


if __name__ == "__main__":
    unittest.main()
