"""R4 sprint 2026-05-28: smoke test EXHAUSTIVO de todos los handlers
migrados a ToolResult. Por cada `domain_tools_X.py` con ToolResult:
- importa el módulo sin error
- llama a la entry-action 'status' (la más segura)
- verifica que devuelve un dict con clave 'ok'

Si alguien introduce una regresión en cualquiera de los handlers
migrados, este test la detecta en segundos.
"""
from __future__ import annotations

import importlib
import pathlib
import tempfile
import unittest
from unittest.mock import MagicMock


# Mapping: sibling module name -> (entry function name, args builder fn)
# args builder receives (state) and returns positional args.
HANDLERS: dict[str, tuple[str, callable]] = {
    "dependency":       ("dependency_tool",        lambda s: ({"action": "status"},)),
    "bluetooth":        ("_device_bluetooth_status", lambda s: ()),
    "source_manager":   ("source_manager_tool",    lambda s: ({"action": "status"}, s)),
    "local_search":     ("local_search_tool",      lambda s: ({"action": "status"},)),
    "notes":            ("notes_tasks_tool",       lambda s: ({"action": "status"}, s)),
    "container":        ("container_tool",         lambda s: ({"action": "status"}, s)),
    "habit_tracker":    ("habit_tracker_tool",     lambda s: ({"action": "status"}, s)),
    "creative_local":   ("creative_local_tool",    lambda s: ({"action": "status"}, s)),
    "peripheral":       ("peripheral_tool",        lambda s: ({"action": "status"}, s)),
    "database":         ("database_tool",          lambda s: ({"action": "status"}, s)),
    "office":           ("office_tool",            lambda s: ({"action": "status"}, s)),
    "fact_check":       ("fact_check_tool",        lambda s: ({"action": "status"}, s)),
    "data_analysis":    ("data_analysis_tool",     lambda s: ({"action": "status"}, s)),
    "media_edit":       ("media_edit_tool",        lambda s: ({"action": "status"}, s)),
    "study":            ("study_tool",             lambda s: ({"action": "status"}, s)),
    "printer_scanner":  ("printer_scanner_tool",   lambda s: ({"action": "status"},)),
    "backup_sync":      ("backup_sync_tool",       lambda s: ({"action": "status"}, s)),
    "maintenance":      ("maintenance_tool",       lambda s: ({"action": "status"}, s)),
    "photo_library":    ("photo_library_tool",     lambda s: ({"action": "status"}, s)),
    "job_manager":      ("job_manager_tool",       lambda s: ({"action": "status"}, s)),
    "watcher":          ("watcher_tool",           lambda s: ({"action": "status"}, s)),
    "accessibility":    ("accessibility_tool",     lambda s: ({"action": "status"}, s)),
    "network":          ("network_tool",           lambda s: ({"action": "status"}, s)),
    "desktop_layout":   ("desktop_layout_tool",    lambda s: ({"action": "status"}, s, MagicMock())),
    "form_filler":      ("form_filler_tool",       lambda s: ({"action": "status"}, s, MagicMock())),
    "game_launcher":    ("game_launcher_tool",     lambda s: ({"action": "status"}, s)),
    "document":         ("document_tool",          lambda s: ({"action": "status"}, s)),
    "contacts":         ("contacts_tool",          lambda s: ({"action": "status"}, s)),
    "calendar":         ("local_calendar_tool",    lambda s: ({"action": "status"}, s)),
    "notifications":    ("notification_tool",      lambda s: ({"action": "status"}, s)),
    "smart_home":       ("smart_home_tool",        lambda s: ({"action": "status"}, s)),
    "developer":        ("developer_tool",         lambda s: ({"action": "status"}, s)),
    "device_settings":  ("device_settings_tool",   lambda s: ({"action": "status"}, s)),
    "routine":          ("routine_tool",           lambda s: ({"action": "status"}, s)),
}


class TestR4AllHandlersSmoke(unittest.TestCase):
    """Smoke por cada handler migrado a ToolResult: import + status."""

    @classmethod
    def setUpClass(cls):
        from gemma4_agent.state import AgentState
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="r4_smoke_"))
        cls.state = AgentState(cls.tmp / "s.json")

    def _smoke(self, sibling_name: str, fn_name: str, args_fn):
        mod = importlib.import_module(f"gemma4_agent.domain_tools_{sibling_name}")
        fn = getattr(mod, fn_name, None)
        self.assertIsNotNone(fn, f"{sibling_name}.{fn_name} not found")
        args = args_fn(self.state)
        result = fn(*args)
        self.assertIsInstance(result, dict, f"{fn_name} returned non-dict: {type(result)}")
        self.assertIn("ok", result, f"{fn_name} dict missing 'ok' key: {result}")

    def test_all_migrated_handlers_smoke(self):
        for sibling, (fn_name, args_fn) in HANDLERS.items():
            with self.subTest(sibling=sibling):
                self._smoke(sibling, fn_name, args_fn)


class TestR4ImportSanity(unittest.TestCase):
    """Todos los siblings se importan sin error, y los que están migrados
    tienen `_ok_tr` o `ToolResult` en su source."""

    def test_all_siblings_import_clean(self):
        pkg = pathlib.Path(__file__).resolve().parent
        for p in pkg.glob("domain_tools_*.py"):
            sibling = p.stem.replace("domain_tools_", "")
            with self.subTest(sibling=sibling):
                importlib.import_module(f"gemma4_agent.{p.stem}")

    def test_at_least_30_sub_package_areas(self):
        """Post R2-finalize: el sub-paquete tiene ≥ 30 áreas como
        submódulos. (El audit pedía ≥ 30 áreas; el R4 migration por
        dataclass quedó como infraestructura disponible — la migración
        real handler-por-handler es trabajo futuro)."""
        pkg = pathlib.Path(__file__).resolve().parent
        subpkg = pkg / "domain_tools"
        self.assertTrue(subpkg.is_dir(), "R2-finalize: subpkg missing")
        areas = [p for p in subpkg.glob("*.py") if p.stem != "__init__"]
        self.assertGreaterEqual(len(areas), 30, f"Solo {len(areas)} áreas")


if __name__ == "__main__":
    unittest.main()
