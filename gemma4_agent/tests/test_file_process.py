"""B6 — file-processor unificado (file_process tool).

Detección por extensión (pura) + delegación end-to-end vía ToolRegistry.execute()
al procesador correcto (data_analysis/document/vision). Gated GEMMA4_FILE_PROCESSOR.
Determinista (sin LLM): valida el ruteo estructural, no la elección del 4B.
"""
import os
import tempfile
import unittest
from pathlib import Path

from ..domain_tools.file_process import (
    detect_file_kind, plan_for_kind, file_processor_enabled,
)


class TestDetectFileKind(unittest.TestCase):
    def test_extensions(self):
        cases = {
            "ventas.csv": "data", "datos.xlsx": "data", "t.tsv": "data",
            "informe.pdf": "document", "doc.docx": "document",
            "p.pptx": "document", "page.html": "document",
            "notas.txt": "text", "script.py": "text",
            "config.yaml": "text", "data.json": "text",
            "foto.jpg": "image", "captura.png": "image", "x.webp": "image",
            "audio.mp3": "audio", "voz.wav": "audio",
            "raro.xyz": "unknown", "sinextension": "unknown",
        }
        for name, kind in cases.items():
            self.assertEqual(detect_file_kind(name), kind, name)

    def test_case_insensitive(self):
        self.assertEqual(detect_file_kind("FOTO.PNG"), "image")
        self.assertEqual(detect_file_kind("DATOS.CSV"), "data")


class TestPlanForKind(unittest.TestCase):
    def test_processable_kinds(self):
        self.assertEqual(plan_for_kind("data"), ("data_analysis", "csv_describe", "path"))
        self.assertEqual(plan_for_kind("document"), ("document", "extract_text", "path"))
        self.assertEqual(plan_for_kind("text"), ("document", "extract_text", "path"))
        self.assertEqual(plan_for_kind("image"), ("vision", "ocr", "image_path"))

    def test_unprocessable_kinds_return_none(self):
        self.assertIsNone(plan_for_kind("audio"))
        self.assertIsNone(plan_for_kind("unknown"))


class TestGate(unittest.TestCase):
    def test_default_off(self):
        prev = os.environ.pop("GEMMA4_FILE_PROCESSOR", None)
        try:
            self.assertFalse(file_processor_enabled())
            os.environ["GEMMA4_FILE_PROCESSOR"] = "1"
            self.assertTrue(file_processor_enabled())
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_FILE_PROCESSOR", None)
            else:
                os.environ["GEMMA4_FILE_PROCESSOR"] = prev


class TestFileProcessIntegration(unittest.TestCase):
    """Delegación real vía execute(). Asertamos la anotación `file_process`
    (kind + delegated_to), no el resultado del backend (depende de pandas/etc.)."""

    def _reg(self):
        from ..memory_pkg.memory import MemoryStore
        from ..memory_pkg.state import AgentState
        from ..tools_pkg.tools import ToolRegistry
        tmp = Path(tempfile.mkdtemp(prefix="gemma4_b6_"))
        memory = MemoryStore(tmp / "mem.json")
        state = AgentState(tmp / "data" / "state.json")
        return ToolRegistry(memory, tmp / "captures", state=state), tmp

    def _set(self, value):
        prev = os.environ.get("GEMMA4_FILE_PROCESSOR")
        if value is None:
            os.environ.pop("GEMMA4_FILE_PROCESSOR", None)
        else:
            os.environ["GEMMA4_FILE_PROCESSOR"] = value
        return prev

    def _restore(self, prev):
        if prev is None:
            os.environ.pop("GEMMA4_FILE_PROCESSOR", None)
        else:
            os.environ["GEMMA4_FILE_PROCESSOR"] = prev

    def test_disabled_when_gate_off(self):
        reg, tmp = self._reg()
        prev = self._set(None)
        try:
            csv = tmp / "x.csv"; csv.write_text("a,b\n1,2\n", encoding="utf-8")
            out = reg.execute("file_process", {"path": str(csv)})
            self.assertFalse(out.get("ok"))
            self.assertIn("disabled", str(out.get("error", "")).lower())
        finally:
            self._restore(prev)

    def test_csv_delegates_to_data_analysis(self):
        reg, tmp = self._reg()
        prev = self._set("1")
        try:
            csv = tmp / "ventas.csv"; csv.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
            out = reg.execute("file_process", {"path": str(csv)})
            fp = out.get("file_process") or {}
            self.assertEqual(fp.get("kind"), "data")
            self.assertEqual(fp.get("delegated_to"), "data_analysis.csv_describe")
        finally:
            self._restore(prev)

    def test_txt_delegates_to_document(self):
        reg, tmp = self._reg()
        prev = self._set("1")
        try:
            txt = tmp / "notas.txt"; txt.write_text("hola mundo\nlinea 2\n", encoding="utf-8")
            out = reg.execute("file_process", {"path": str(txt)})
            fp = out.get("file_process") or {}
            self.assertEqual(fp.get("kind"), "text")
            self.assertEqual(fp.get("delegated_to"), "document.extract_text")
        finally:
            self._restore(prev)

    def test_nonexistent_file_needs_user(self):
        reg, tmp = self._reg()
        prev = self._set("1")
        try:
            out = reg.execute("file_process", {"path": str(tmp / "noexiste.pdf")})
            self.assertFalse(out.get("ok"))
            self.assertEqual(out.get("status"), "needs_user")
        finally:
            self._restore(prev)

    def test_audio_not_wired_returns_kind(self):
        reg, tmp = self._reg()
        prev = self._set("1")
        try:
            wav = tmp / "voz.wav"; wav.write_bytes(b"RIFF0000WAVE")
            out = reg.execute("file_process", {"path": str(wav)})
            self.assertFalse(out.get("ok"))
            self.assertEqual(out.get("file_kind"), "audio")
        finally:
            self._restore(prev)


if __name__ == "__main__":
    unittest.main()
