"""Routing override por extensión (2026-05-29): lectura/análisis de archivos de
datos/documento -> tool específica (data_analysis/document), no filesystem.read.
Tests de la función pura _route_file_by_extension + el gate. El efecto en vivo
(que el 4B elija la tool) es no-determinista -> validado aparte (1/6 -> 4/6)."""
import os
import unittest
from pathlib import Path

from ..agent_core.agent import _route_file_by_extension, _file_tool_routing_enabled


class TestRouteFileByExtension(unittest.TestCase):
    def test_csv_swaps_filesystem_for_data_analysis(self):
        out = _route_file_by_extension("analizá ventas.csv", ["filesystem", "office"])
        self.assertNotIn("filesystem", out)
        self.assertIn("data_analysis", out)

    def test_xlsx_routes_to_data_analysis(self):
        out = _route_file_by_extension("resumime datos.xlsx", ["filesystem"])
        self.assertIn("data_analysis", out)
        self.assertNotIn("filesystem", out)

    def test_pdf_adds_document_keeps_filesystem(self):
        # DOC es additivo: document disponible + filesystem QUEDA. Sacar fs empeoraba
        # a "sin-tool" (el 4B insiste en filesystem.read); filesystem.read delega a
        # document para binarios (handler-delegation en tools.py).
        out = _route_file_by_extension("qué dice reporte.pdf", ["filesystem", "web"])
        self.assertIn("document", out)
        self.assertIn("filesystem", out)
        self.assertIn("web", out)

    def test_docx_pptx_html_add_document(self):
        for fn in ("informe.docx", "charla.pptx", "pagina.html"):
            out = _route_file_by_extension(f"leeme {fn}", ["filesystem"])
            self.assertIn("document", out, fn)  # additivo (filesystem queda + delega)

    def test_fileop_keeps_filesystem(self):
        # verbo de file-op -> filesystem se queda (no romper mover/borrar/copiar)
        for cmd in ("borrá ventas.csv", "mové reporte.pdf a Documentos",
                    "copiá datos.xlsx al escritorio", "renombrá informe.docx"):
            out = _route_file_by_extension(cmd, ["filesystem"])
            self.assertIn("filesystem", out, cmd)

    def test_no_extension_no_change(self):
        names = ["filesystem", "web", "app"]
        self.assertEqual(_route_file_by_extension("analizá mis cosas", names), names)

    def test_local_file_search_routes_to_filesystem(self):
        # "buscá un word en documentos" -> filesystem (local), NO web (internet).
        for cmd in ("buscá un word en mis documentos", "listá los archivos de descargas",
                    "buscá un pdf en el escritorio", "mostrame las fotos de mi carpeta"):
            out = _route_file_by_extension(cmd, ["web", "browser"])
            self.assertIn("filesystem", out, cmd)
            self.assertNotIn("web", out, cmd)

    def test_generic_web_search_not_touched(self):
        # búsqueda web genérica (sin carpeta local ni tipo de archivo) -> web se queda
        for cmd in ("buscá noticias de hoy", "qué es la fotosíntesis", "buscá recetas"):
            out = _route_file_by_extension(cmd, ["web"])
            self.assertIn("web", out, cmd)

    def test_idempotent_when_data_analysis_present(self):
        out = _route_file_by_extension("analizá ventas.csv", ["data_analysis"])
        self.assertEqual(out.count("data_analysis"), 1)

    def test_gate_default_on(self):
        # 2026-05-29: flipeado a default-ON (validado 6/6 en vivo + suite verde).
        # El kill-switch GEMMA4_FILE_TOOL_ROUTING=0 sigue funcionando.
        prev = os.environ.pop("GEMMA4_FILE_TOOL_ROUTING", None)
        try:
            self.assertTrue(_file_tool_routing_enabled())  # default ON ahora
            os.environ["GEMMA4_FILE_TOOL_ROUTING"] = "0"
            self.assertFalse(_file_tool_routing_enabled())  # kill-switch
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_FILE_TOOL_ROUTING", None)
            else:
                os.environ["GEMMA4_FILE_TOOL_ROUTING"] = prev


class TestFilesystemReadDelegation(unittest.TestCase):
    """Handler-delegation: cuando el 4B usa filesystem.read sobre un PDF/Word/PPT
    (prior arraigado), el handler delega a document.extract_text -> texto real en
    vez de binario inútil. Gated por GEMMA4_FILE_TOOL_ROUTING."""
    def _reg(self):
        import tempfile
        from ..tools_pkg.tools import ToolRegistry
        reg = ToolRegistry.__new__(ToolRegistry)
        self._calls = []
        reg.t_document = lambda a: (self._calls.append(a) or
                                    {"ok": True, "text": "TEXTO REAL", "action": "extract_text"})
        self._tmp = Path(tempfile.mkdtemp())
        return reg

    def _run(self, filename, content=b"data", flag="1"):
        reg = self._reg()
        p = self._tmp / filename
        p.write_bytes(content)
        prev = os.environ.get("GEMMA4_FILE_TOOL_ROUTING")
        os.environ["GEMMA4_FILE_TOOL_ROUTING"] = flag
        try:
            return reg.filesystem_read({"path": str(p)})
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_FILE_TOOL_ROUTING", None)
            else:
                os.environ["GEMMA4_FILE_TOOL_ROUTING"] = prev

    def test_pdf_read_delegates_to_document(self):
        out = self._run("doc.pdf")
        self.assertEqual(out.get("text"), "TEXTO REAL")
        self.assertEqual(self._calls[0].get("action"), "extract_text")

    def test_docx_read_delegates(self):
        out = self._run("informe.docx")
        self.assertEqual(out.get("text"), "TEXTO REAL")

    def test_txt_read_NOT_delegated(self):
        # texto plano -> lectura normal (no delega a document)
        out = self._run("notas.txt", content=b"hola mundo")
        self.assertEqual(self._calls, [])
        self.assertIn("hola mundo", out.get("content", ""))

    def test_pdf_not_delegated_when_off(self):
        out = self._run("doc.pdf", content=b"%PDF plain text no nul", flag="0")
        self.assertEqual(self._calls, [])  # gate off -> lectura normal


if __name__ == "__main__":
    unittest.main()
