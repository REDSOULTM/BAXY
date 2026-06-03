"""R2 finalize sprint 2026-05-28: tests de integridad del sub-paquete
`gemma4_agent.domain_tools/`.

Verifica:
- El paquete se importa limpio.
- Los 36 submódulos se importan sin error.
- Los shims `domain_tools_<area>.py` apuntan al MISMO objeto-módulo que
  el submódulo `domain_tools.<area>` (identidad, no copia).
- Symbols principales (entry tools) accesibles desde múltiples paths.
- Cross-area imports dentro del paquete resuelven correctamente.
"""
from __future__ import annotations

import importlib
import unittest


# Áreas del sub-paquete (las que tienen handler entry)
PKG_AREAS = [
    "accessibility", "backup_sync", "bluetooth", "calendar", "contacts",
    "container", "creative_local", "data_analysis", "database", "dependency",
    "desktop_layout", "developer", "device_settings", "document",
    "fact_check", "form_filler", "game_launcher", "habit_tracker",
    "helpers", "job_manager", "local_search", "maintenance", "media_edit",
    "network", "notes", "notifications", "office", "peripheral",
    "photo_library", "printer_scanner", "routine",
    "source_manager", "study", "watcher", "wifi",
]


class TestR2SubpkgIntegrity(unittest.TestCase):
    """Sub-paquete `domain_tools/` está bien armado."""

    def test_subpkg_imports(self):
        from gemma4_agent import domain_tools
        # El paquete debe re-exportar los símbolos principales
        self.assertTrue(hasattr(domain_tools, "_ok"))
        self.assertTrue(hasattr(domain_tools, "_err"))

    def test_all_areas_importable(self):
        for area in PKG_AREAS:
            with self.subTest(area=area):
                mod = importlib.import_module(f"gemma4_agent.domain_tools.{area}")
                self.assertIsNotNone(mod)

    def test_shim_is_same_object_as_subpkg_module(self):
        """`gemma4_agent.domain_tools_<area>` ES el mismo objeto-módulo que
        `gemma4_agent.domain_tools.<area>` — gracias al sys.modules aliasing
        del shim. Esto garantiza que mocks viejos sobre el path antiguo
        llegan al sitio real."""
        for area in PKG_AREAS:
            with self.subTest(area=area):
                shim = importlib.import_module(f"gemma4_agent.domain_tools_{area}")
                real = importlib.import_module(f"gemma4_agent.domain_tools.{area}")
                self.assertIs(shim, real, f"Shim {area} no es el real")

    def test_canonical_entry_tools_accessible(self):
        """Verifica que las tools de cada área están accesibles."""
        cases = [
            ("dependency", "dependency_tool"),
            ("bluetooth", "_device_bluetooth_status"),
            ("source_manager", "source_manager_tool"),
            ("local_search", "local_search_tool"),
            ("notes", "notes_tasks_tool"),
            ("container", "container_tool"),
            ("habit_tracker", "habit_tracker_tool"),
            ("creative_local", "creative_local_tool"),
            ("peripheral", "peripheral_tool"),
            ("database", "database_tool"),
            ("office", "office_tool"),
            ("fact_check", "fact_check_tool"),
            ("data_analysis", "data_analysis_tool"),
            ("media_edit", "media_edit_tool"),
            ("study", "study_tool"),
            ("printer_scanner", "printer_scanner_tool"),
            ("backup_sync", "backup_sync_tool"),
            ("maintenance", "maintenance_tool"),
            ("photo_library", "photo_library_tool"),
            ("job_manager", "job_manager_tool"),
            ("watcher", "watcher_tool"),
            ("accessibility", "accessibility_tool"),
            ("network", "network_tool"),
            ("desktop_layout", "desktop_layout_tool"),
            ("form_filler", "form_filler_tool"),
            ("game_launcher", "game_launcher_tool"),
            ("document", "document_tool"),
            ("contacts", "contacts_tool"),
            ("calendar", "local_calendar_tool"),
            ("notifications", "notification_tool"),
            ("developer", "developer_tool"),
            ("device_settings", "device_settings_tool"),
            ("routine", "routine_tool"),
        ]
        for area, fn_name in cases:
            with self.subTest(area=area, fn=fn_name):
                mod = importlib.import_module(f"gemma4_agent.domain_tools.{area}")
                self.assertTrue(hasattr(mod, fn_name),
                                f"{area}.{fn_name} not exported")

    def test_helpers_module_exports_13_helpers(self):
        from gemma4_agent.domain_tools import helpers
        expected = {
            "_existing_path", "_find_resource", "_find_routine",
            "_find_soundvolumeview", "_json_or_none", "_parse_due_iso",
            "_pid_alive", "_pid_owned_by", "_powershell_json", "_ps_quote",
            "_resources_by_kind", "_safe_name", "_update_resource_metadata",
        }
        actual = set(getattr(helpers, "__all__", []))
        self.assertEqual(actual, expected,
                         f"helpers.__all__ mismatch. Missing: {expected - actual}")

    def test_cross_area_lazy_imports_resolve(self):
        """Las áreas que importan helpers LAZY (dentro de funciones) deben
        resolver al llamar el handler."""
        from gemma4_agent.domain_tools.source_manager import source_manager_tool
        from gemma4_agent.memory_pkg.state import AgentState
        import tempfile, pathlib
        s = AgentState(pathlib.Path(tempfile.mkdtemp()) / "s.json")
        # Hace el lazy import por dentro: from .helpers import _existing_path, ...
        r = source_manager_tool({"action": "status"}, s)
        self.assertTrue(r["ok"])


if __name__ == "__main__":
    unittest.main()
