"""filesystem.search debe resolver `path` y carpetas de usuario (bug #847).

Bug: el LLM pasa `path="Downloads"` (intuitivo, está en el schema) pero
filesystem_search solo leía `root`, default "." -> buscaba en el dir del
PROYECTO, no en Downloads. Por eso 'abre el Word de Descargas' nunca encontraba
los archivos reales del usuario.

Fix: aceptar path/dir como alias de root + mapear nombres de carpetas conocidas
(Downloads/Descargas/Escritorio/Documentos...) al home real.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from gemma4_agent.tools import ToolRegistry


class UserFolderResolveTest(unittest.TestCase):
    def setUp(self):
        self.reg = ToolRegistry.__new__(ToolRegistry)

    def test_downloads_es_en(self):
        home = str(Path.home())
        for name in ("Downloads", "descargas", "DESCARGAS"):
            got = str(self.reg._resolve_user_folder(name))
            self.assertTrue(got.startswith(home), f"{name} -> {got}")
            self.assertTrue(got.endswith("Downloads"), f"{name} -> {got}")

    def test_other_known_folders(self):
        cases = {"Escritorio": "Desktop", "Documentos": "Documents",
                 "Imágenes": "Pictures", "Música": "Music"}
        for raw, expect in cases.items():
            got = str(self.reg._resolve_user_folder(raw))
            self.assertTrue(got.endswith(expect), f"{raw} -> {got}")

    def test_explicit_path_untouched(self):
        # una ruta explícita NO debe mapearse a una carpeta de usuario
        got = self.reg._resolve_user_folder("C:/temp/x")
        self.assertIn("temp", str(got))

    def test_search_accepts_path_alias(self):
        # search debe leer `path` como alias de `root` (lo que el LLM manda)
        import inspect
        src = inspect.getsource(ToolRegistry.filesystem_search)
        self.assertIn('args.get("path")', src,
                      "filesystem_search debe aceptar `path` como alias de root")


if __name__ == "__main__":
    unittest.main()
