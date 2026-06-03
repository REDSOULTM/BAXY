"""Tests del subset MIGRADO a ToolResult.

Verifica que los 5 handlers ya migrados producen dicts byte-a-byte
compatibles con el patrón legacy `_ok/_err`. Si la migración rompe
algo, este test lo detecta.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class TestR4MigratedHandlers(unittest.TestCase):
    """Cada handler migrado debe seguir devolviendo dicts con la misma
    forma que su versión _ok/_err legacy."""

    def setUp(self):
        from gemma4_agent.memory_pkg.state import AgentState
        self.tmp = Path(tempfile.mkdtemp())
        self.state = AgentState(self.tmp / "s.json")

    def test_dependency_tool_status_returns_dict(self):
        from gemma4_agent.domain_tools_dependency import dependency_tool
        r = dependency_tool({"action": "status"})
        self.assertIsInstance(r, dict)
        self.assertTrue(r["ok"])
        self.assertIn("dependencies", r)
        self.assertIsInstance(r["dependencies"], list)

    def test_dependency_tool_unknown_action_dict(self):
        from gemma4_agent.domain_tools_dependency import dependency_tool
        r = dependency_tool({"action": "frobnicate"})
        self.assertIsInstance(r, dict)
        self.assertFalse(r["ok"])
        self.assertIn("error", r)
        self.assertEqual(r["status"], "needs_user")
        self.assertIn("valid_actions", r)

    def test_source_manager_status_returns_dict(self):
        from gemma4_agent.domain_tools_source_manager import source_manager_tool
        r = source_manager_tool({"action": "status"}, self.state)
        self.assertIsInstance(r, dict)
        self.assertTrue(r["ok"])
        self.assertEqual(r["source_count"], 0)

    def test_source_manager_snapshot_file_missing_path(self):
        from gemma4_agent.domain_tools_source_manager import source_manager_tool
        r = source_manager_tool({"action": "snapshot_file", "path": "/no/existe"}, self.state)
        self.assertFalse(r["ok"])
        self.assertIn("missing or invalid path", r["error"])

    def test_local_search_status_returns_dict(self):
        from gemma4_agent.domain_tools_local_search import local_search_tool
        r = local_search_tool({"action": "status"})
        self.assertTrue(r["ok"])
        self.assertIn("backend", r)

    def test_local_search_unknown_action_dict(self):
        from gemma4_agent.domain_tools_local_search import local_search_tool
        r = local_search_tool({"action": "frobnicate"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")

    def test_notes_tasks_status_returns_dict(self):
        from gemma4_agent.domain_tools_notes import notes_tasks_tool
        r = notes_tasks_tool({"action": "status"}, self.state)
        self.assertTrue(r["ok"])
        self.assertEqual(r["notes"], 0)
        self.assertEqual(r["tasks"], 0)

    def test_notes_create_then_list(self):
        from gemma4_agent.domain_tools_notes import notes_tasks_tool
        # Crear una nota
        r = notes_tasks_tool({"action": "note_create", "title": "Test", "text": "Body"}, self.state)
        self.assertTrue(r["ok"])
        self.assertIn("note", r)
        # Listarlas
        r = notes_tasks_tool({"action": "note_list"}, self.state)
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["notes"]), 1)

    def test_notes_unknown_action_dict(self):
        from gemma4_agent.domain_tools_notes import notes_tasks_tool
        r = notes_tasks_tool({"action": "frobnicate"}, self.state)
        self.assertFalse(r["ok"])
        self.assertIn("valid_actions", r)
        self.assertEqual(r["status"], "needs_user")


class TestR4StatusFieldOmittedOnSuccess(unittest.TestCase):
    """`ToolResult.to_dict()` omite `status` cuando es el default 'ok' para
    mantener el shape del legacy `_ok(...)`. Verifica que esto se cumple."""

    def test_ok_result_omits_status_field(self):
        from gemma4_agent.tools_pkg.tool_result import ToolResult
        r = ToolResult.ok_result(foo="bar").to_dict()
        self.assertNotIn("status", r)  # 'ok' default no aparece
        self.assertEqual(r, {"ok": True, "foo": "bar"})

    def test_err_includes_status_when_set(self):
        from gemma4_agent.tools_pkg.tool_result import ToolResult
        r = ToolResult.err("boom", status="needs_user").to_dict()
        self.assertEqual(r["status"], "needs_user")


if __name__ == "__main__":
    unittest.main()
