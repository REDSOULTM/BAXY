"""R3 follow-up 2026-05-28: tests unitarios de los 13 helpers
cross-cutting de `gemma4_agent.domain_tools.helpers`.

Cada helper es usado por múltiples siblings; un bug acá rompe todo el
área. Estos tests dan cobertura unitaria mínima — no end-to-end con
PowerShell sino lógica pura.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemma4_agent.domain_tools.helpers import (
    _existing_path,
    _find_resource,
    _find_routine,
    _json_or_none,
    _parse_due_iso,
    _resources_by_kind,
    _safe_name,
    _update_resource_metadata,
    _ps_quote,
)
from gemma4_agent.state import AgentState


class TestExistingPath(unittest.TestCase):

    def test_returns_none_when_missing_arg(self):
        self.assertIsNone(_existing_path({}))

    def test_returns_none_when_empty_string(self):
        self.assertIsNone(_existing_path({"path": ""}))

    def test_returns_none_when_path_doesnt_exist(self):
        self.assertIsNone(_existing_path({"path": "/nonexistent/path/here"}))

    def test_returns_path_when_exists(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            tmp = f.name
        try:
            result = _existing_path({"path": tmp})
            self.assertIsNotNone(result)
            self.assertIsInstance(result, Path)
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_expands_user_home(self):
        # `~/something` debe expandirse aunque no exista
        result = _existing_path({"path": "~/nonexistent_xyz_test"})
        # Devuelve None porque no existe (pero no crash)
        self.assertIsNone(result)


class TestJsonOrNone(unittest.TestCase):

    def test_valid_json_dict(self):
        self.assertEqual(_json_or_none('{"a": 1}'), {"a": 1})

    def test_empty_string(self):
        self.assertIsNone(_json_or_none(""))

    def test_invalid_json(self):
        self.assertIsNone(_json_or_none("not json"))

    def test_non_dict_json(self):
        """Solo dicts son aceptados — listas, primitives → None."""
        self.assertIsNone(_json_or_none("[1, 2]"))
        self.assertIsNone(_json_or_none("42"))


class TestParseDueIso(unittest.TestCase):

    def test_none_returns_none_no_error(self):
        iso, err = _parse_due_iso(None)
        self.assertIsNone(iso)
        self.assertIsNone(err)

    def test_empty_returns_none_no_error(self):
        iso, err = _parse_due_iso("")
        self.assertIsNone(iso)
        self.assertIsNone(err)

    def test_date_only_adds_t00(self):
        iso, err = _parse_due_iso("2026-05-20")
        self.assertEqual(iso, "2026-05-20T00:00:00")
        self.assertIsNone(err)

    def test_date_with_time_adds_seconds(self):
        iso, err = _parse_due_iso("2026-05-20T15:30")
        self.assertEqual(iso, "2026-05-20T15:30:00")
        self.assertIsNone(err)

    def test_full_iso_passthrough(self):
        iso, err = _parse_due_iso("2026-05-20T15:30:45")
        self.assertEqual(iso, "2026-05-20T15:30:45")
        self.assertIsNone(err)

    def test_natural_language_rejected(self):
        iso, err = _parse_due_iso("mañana")
        self.assertIsNone(iso)
        self.assertIsNotNone(err)
        self.assertIn("ISO 8601", err)

    def test_non_string_rejected(self):
        iso, err = _parse_due_iso(123)
        self.assertIsNone(iso)
        self.assertIsNotNone(err)


class TestSafeName(unittest.TestCase):

    def test_safe_chars_preserved(self):
        self.assertEqual(_safe_name("hello_world"), "hello_world")

    def test_unsafe_chars_replaced(self):
        # Espacio / signos se vuelven _
        self.assertEqual(_safe_name("hello world"), "hello_world")

    def test_truncated_to_50_chars(self):
        long_name = "a" * 100
        self.assertEqual(len(_safe_name(long_name)), 50)

    def test_empty_returns_archivo(self):
        self.assertEqual(_safe_name(""), "archivo")

    def test_only_special_returns_archivo(self):
        # Si todos los chars son raros y stripeados, fallback
        self.assertEqual(_safe_name("///"), "archivo")


class TestPsQuote(unittest.TestCase):

    def test_no_quotes_passthrough(self):
        self.assertEqual(_ps_quote("hello"), "hello")

    def test_single_quote_doubled(self):
        # PowerShell escape: ' → ''
        self.assertEqual(_ps_quote("it's"), "it''s")

    def test_multiple_single_quotes(self):
        self.assertEqual(_ps_quote("'a'b'"), "''a''b''")


class TestResourceHelpers(unittest.TestCase):
    """_find_resource, _resources_by_kind, _find_routine,
    _update_resource_metadata trabajan sobre AgentState."""

    def setUp(self):
        tmp = Path(tempfile.mkdtemp(prefix="gemma4_helpers_"))
        self.state = AgentState(tmp / "s.json")

    def test_resources_by_kind_empty(self):
        out = _resources_by_kind(self.state, "note")
        self.assertEqual(out, [])

    def test_find_resource_returns_none_when_empty(self):
        result = _find_resource({"query": "anything"}, self.state, "note")
        self.assertIsNone(result)

    def test_find_routine_returns_none_when_empty(self):
        result = _find_routine({"name": "anything"}, self.state)
        self.assertIsNone(result)

    def test_resources_by_kind_with_data(self):
        # Crear un recurso
        self.state.register_resource("note", "Test note", metadata={"text": "hello"})
        out = _resources_by_kind(self.state, "note")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["label"], "Test note")

    def test_resources_by_kind_multiple_kinds(self):
        # Buscar varios kinds en una llamada
        self.state.register_resource("note", "N1")
        self.state.register_resource("task", "T1")
        out = _resources_by_kind(self.state, ["note", "task"])
        self.assertEqual(len(out), 2)

    def test_update_resource_metadata_unknown_returns_err(self):
        result = _update_resource_metadata(self.state, "unknown_id_xyz", {"x": 1})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "resource not found")


if __name__ == "__main__":
    unittest.main()
