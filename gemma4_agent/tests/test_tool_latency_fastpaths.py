"""Fast-paths de latencia de tools no-web (2026-06-09). MEDIDO: varias tools
read-only/status pagaban PowerShell+WMI o stat()-por-archivo. Estos tests fijan
el CONTRATO de los fast-paths (no la latencia absoluta, que depende del hardware):
formato de salida estable + el fallback sigue disponible.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.memory_pkg.memory import MemoryStore
from gemma4_agent.memory_pkg.state import AgentState


def _reg() -> ToolRegistry:
    tmp = Path(tempfile.mkdtemp())
    return ToolRegistry(MemoryStore(tmp / "m.json"), tmp / "cap",
                        state=AgentState(tmp / "s.json"), safety_enabled=False)


class TestCpuRamGpuFastPath(unittest.TestCase):
    def test_output_shape_preserved(self):
        # El dict `info` conserva las claves cpu/os/gpu que el LLM lee.
        r = _reg().execute("system", {"action": "cpu_ram_gpu"})
        self.assertTrue(r.get("ok") is not False, r)
        info = r.get("info") or {}
        self.assertIn("cpu", info)
        self.assertIn("os", info)
        self.assertIn("gpu", info)
        # source delata el camino: psutil+nvidia-smi (rápido) o wmi (fallback).
        self.assertIn(r.get("source"), {"psutil+nvidia-smi", "wmi", None})

    def test_ram_values_present(self):
        r = _reg().execute("system", {"action": "cpu_ram_gpu"})
        os_info = (r.get("info") or {}).get("os") or {}
        # KB (como WMI). > 0 si psutil leyó la RAM.
        self.assertGreater(int(os_info.get("TotalVisibleMemorySize") or 0), 0)


class TestAudioDevicesCache(unittest.TestCase):
    def test_second_call_is_cached(self):
        reg = _reg()
        r1 = reg.execute("audio", {"action": "devices"})
        self.assertTrue(r1.get("ok") is not False)
        r2 = reg.execute("audio", {"action": "devices"})
        self.assertTrue(r2.get("cached") is True or r2.get("source") == "cache",
                        f"2da consulta debería venir del cache: {r2.get('source')}")

    def test_refresh_bypasses_cache(self):
        reg = _reg()
        reg.execute("audio", {"action": "devices"})
        r = reg.execute("audio", {"action": "devices", "refresh": True})
        self.assertNotEqual(r.get("source"), "cache")


class TestLocalSearchDeferStat(unittest.TestCase):
    def test_name_search_returns_results_with_expected_fields(self):
        # Crea un árbol pequeño y busca por nombre; el resultado debe traer los
        # campos path/is_file/size aunque ahora difiramos stat() a los hits.
        tmp = Path(tempfile.mkdtemp())
        (tmp / "alpha_report.txt").write_text("x", encoding="utf-8")
        (tmp / "sub").mkdir()
        (tmp / "sub" / "beta_alpha.md").write_text("y", encoding="utf-8")
        from gemma4_agent.domain_tools.local_search import local_search_tool
        r = local_search_tool({"action": "search", "root": str(tmp),
                               "query": "alpha", "limit": 50})
        self.assertTrue(r.get("ok") is not False, r)
        names = [Path(h["path"]).name for h in r.get("results", [])]
        self.assertIn("alpha_report.txt", names)
        self.assertIn("beta_alpha.md", names)
        for h in r.get("results", []):
            self.assertIn("path", h)
            self.assertIn("is_file", h)

    def test_content_search_still_reads_files(self):
        # Con include_content, un archivo cuyo NOMBRE no matchea pero su CONTENIDO
        # sí, debe encontrarse (no lo saltamos por el defer de stat).
        tmp = Path(tempfile.mkdtemp())
        (tmp / "notes.txt").write_text("la palabra secreta es zarpa", encoding="utf-8")
        from gemma4_agent.domain_tools.local_search import local_search_tool
        r = local_search_tool({"action": "search", "root": str(tmp),
                               "query": "zarpa", "include_content": True, "limit": 50})
        names = [Path(h["path"]).name for h in r.get("results", [])]
        self.assertIn("notes.txt", names)


class TestScreenshotContract(unittest.TestCase):
    def test_primary_origin_is_zero(self):
        # El primario de Windows tiene origen (0,0). El fast-path mss DEBE elegir
        # ese monitor (no un mons[1] que puede estar en left<0) — si no, los clicks
        # caerían en la pantalla equivocada.
        r = _reg().execute("gui", {"action": "screenshot", "monitor": "primary"})
        if r.get("source") == "mss":  # solo si mss está disponible
            self.assertEqual(int(r.get("left")), 0)
            self.assertEqual(int(r.get("top")), 0)
        # contrato: siempre devuelve image_path + dimensiones
        self.assertTrue(r.get("ok") is not False, r)
        self.assertTrue(r.get("image_path"))
        self.assertGreater(int(r.get("width") or 0), 0)


if __name__ == "__main__":
    unittest.main()
