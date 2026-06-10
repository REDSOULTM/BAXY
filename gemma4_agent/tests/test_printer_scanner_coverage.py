"""Cobertura dedicada para domain_tools/printer_scanner.py (added 2026-06-01).

printer_scanner.py NO tenía test propio (solo el smoke {action:status}).
Cubre imprimir/escanear/listar con TODO subprocess (PowerShell + WIA) mockeado
— jamás se toca una impresora/escáner real ni se imprime nada.

Detalle de mocking: printer_scanner enruta varias acciones por
helpers._powershell_json / helpers._json_or_none. Verificado que
printer_scanner.subprocess y helpers.subprocess son el MISMO objeto-módulo,
así que parchear `subprocess.run` (el global compartido) intercepta ambos
caminos con un solo patch.

Propiedades afirmadas contra el código fuente:
  - honestidad: verified refleja returncode/queue-probe, no se inventa éxito
  - returncode!=0 -> ok:False
  - JSON inválido -> ok:False
  - print_file/scan exigen un archivo/destino válido
  - WIA sin escáneres -> lista vacía o needs_dependency, nunca mentira
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ..domain_tools import printer_scanner


def _proc(returncode=0, stdout="", stderr=""):
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


class TestPrinterScannerEntry(unittest.TestCase):
    def test_status(self):
        r = printer_scanner.printer_scanner_tool({"action": "status"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["backend"], "Windows PrintManagement")

    def test_unknown_action(self):
        r = printer_scanner.printer_scanner_tool({"action": "explode"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")

    def test_printers_list_parses_json(self):
        with patch.object(subprocess, "run", return_value=_proc(0, '[{"Name":"HP LaserJet"}]')):
            r = printer_scanner.printer_scanner_tool({"action": "printers_list"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 1)

    def test_printers_list_powershell_failure(self):
        with patch.object(subprocess, "run", return_value=_proc(1, "", "no spooler")):
            r = printer_scanner.printer_scanner_tool({"action": "printers_list"})
        self.assertFalse(r["ok"])

    def test_printers_list_invalid_json(self):
        with patch.object(subprocess, "run", return_value=_proc(0, "not-json{")):
            r = printer_scanner.printer_scanner_tool({"action": "printers_list"})
        self.assertFalse(r["ok"])


class TestPrinterSetDefault(unittest.TestCase):
    def test_missing_name(self):
        self.assertFalse(printer_scanner._printer_set_default({})["ok"])

    def test_success_marks_verified(self):
        with patch.object(subprocess, "run", return_value=_proc(0, '{"Name":"HP"}')):
            r = printer_scanner._printer_set_default({"name": "HP"})
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"])
        self.assertEqual(r["printer"], "HP")

    def test_failure_not_verified(self):
        with patch.object(subprocess, "run", return_value=_proc(1, "", "no such printer")):
            r = printer_scanner._printer_set_default({"name": "Ghost"})
        self.assertFalse(r["ok"])


class TestPrinterPrintFile(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="prn_cov_"))

    def test_missing_path(self):
        self.assertFalse(printer_scanner._printer_print_file({})["ok"])

    def test_file_not_found(self):
        self.assertFalse(
            printer_scanner._printer_print_file({"path": str(self.tmp / "ghost.pdf")})["ok"])

    def test_print_failure_returncode(self):
        doc = self.tmp / "doc.txt"
        doc.write_text("hello", encoding="utf-8")
        with patch.object(subprocess, "run", return_value=_proc(1, "", "print error")):
            r = printer_scanner._printer_print_file({"path": str(doc)})
        self.assertFalse(r["ok"])

    def test_print_verified_reflects_queue_probe(self):
        # HONESTIDAD: verified = bool(queue_probe.ok). Si el queue-probe no halla
        # un job (lista vacía), verified debe ser True solo si el probe corrió ok.
        doc = self.tmp / "doc.txt"
        doc.write_text("hello", encoding="utf-8")
        # primer run: print (rc 0, devuelve JSON con previous); segundo: queue probe
        with patch.object(subprocess, "run",
                          side_effect=[_proc(0, '{"ok": true, "previous": "HP"}'),
                                       _proc(0, '[{"ID": 5, "JobStatus": "Printing"}]')]):
            r = printer_scanner._printer_print_file({"path": str(doc), "printer": "HP"})
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"])
        self.assertEqual(r["printer"], "HP")


class TestPrinterCancelJob(unittest.TestCase):
    def test_missing_printer(self):
        self.assertFalse(printer_scanner._printer_cancel_job({})["ok"])

    def test_cancel_all_when_no_job_id(self):
        with patch.object(subprocess, "run", return_value=_proc(0, '{"ok": true}')):
            r = printer_scanner._printer_cancel_job({"printer": "HP"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["cancelled"], "all")

    def test_cancel_specific_job(self):
        with patch.object(subprocess, "run", return_value=_proc(0, '{"ok": true}')):
            r = printer_scanner._printer_cancel_job({"printer": "HP", "job_id": 7})
        self.assertTrue(r["ok"])
        self.assertEqual(r["cancelled"], 7)

    def test_cancel_failure(self):
        with patch.object(subprocess, "run", return_value=_proc(1, "", "err")):
            self.assertFalse(printer_scanner._printer_cancel_job({"printer": "HP"})["ok"])


class TestScannersList(unittest.TestCase):
    def test_empty_output_no_devices(self):
        with patch.object(subprocess, "run", return_value=_proc(0, "")):
            r = printer_scanner._scanners_list()
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 0)

    def test_devices_listed(self):
        with patch.object(subprocess, "run",
                          return_value=_proc(0, '[{"Name":"Canon","DeviceID":"x"}]')):
            r = printer_scanner._scanners_list()
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 1)

    def test_wia_error_is_needs_dependency(self):
        # El script PS devuelve {error: ...} cuando WIA falla -> needs_dependency,
        # nunca una lista de escáneres inventada.
        with patch.object(subprocess, "run",
                          return_value=_proc(0, '{"error":"WIA not available"}')):
            r = printer_scanner._scanners_list()
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_dependency")

    def test_invalid_json(self):
        with patch.object(subprocess, "run", return_value=_proc(0, "garbage{")):
            self.assertFalse(printer_scanner._scanners_list()["ok"])


class TestScannerScan(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="scan_cov_"))

    def test_no_scanner_connected_is_needs_dependency(self):
        # WIA reporta "No scanner connected" -> needs_dependency, no miente éxito.
        out = self.tmp / "scan.jpg"
        with patch.object(subprocess, "run",
                          return_value=_proc(0, '{"ok": false, "error": "No scanner connected"}')):
            r = printer_scanner._scanner_scan({"output": str(out)})
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_dependency")

    def test_scan_subprocess_failure(self):
        out = self.tmp / "scan.jpg"
        with patch.object(subprocess, "run", return_value=_proc(1, "", "wia crash")):
            r = printer_scanner._scanner_scan({"output": str(out)})
        self.assertFalse(r["ok"])

    def test_scan_success_verified_requires_file(self):
        # El PS reporta ok=true; pero verified = out.exists(). Como mockeamos el
        # subprocess, el archivo NO existe -> verified debe ser False (honestidad).
        out = self.tmp / "scan.jpg"
        with patch.object(subprocess, "run",
                          return_value=_proc(0, '{"ok": true, "path": "' + str(out).replace("\\", "/") + '"}')):
            r = printer_scanner._scanner_scan({"output": str(out)})
        self.assertTrue(r["ok"])
        self.assertFalse(r["verified"])  # el archivo no se creó realmente


if __name__ == "__main__":
    unittest.main()
