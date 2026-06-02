"""Cobertura dedicada para domain_tools/maintenance.py (added 2026-06-01).

maintenance.py NO tenía test propio (solo el smoke {action:status}).
Cubre las acciones de diagnóstico Windows con TODO subprocess mockeado
(CLAUDE.md: nada de PowerShell/Defender/servicios reales en tests).

Propiedades afirmadas contra el código fuente:
  - honestidad: verified refleja returncode; returncode!=0 -> ok:False
  - JSON inválido del PowerShell -> ok:False (no crash, no mentira)
  - guarda de inyección event_logs_query (allowlist RX_LOG_NAME)
  - hours/limit/level no-enteros -> needs_user
  - acciones destructivas no expuestas (disk_cleanup execution / update install)
  - service_control corre con checkpoint (rollback) y verifica el resultado
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ..domain_tools import maintenance
from ..memory_pkg.state import AgentState


def _proc(returncode=0, stdout="", stderr=""):
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


class TestMaintenanceEntry(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="maint_cov_"))
        self.state = AgentState(self.tmp / "s.json")

    def test_status(self):
        r = maintenance.maintenance_tool({"action": "status"}, self.state)
        self.assertTrue(r["ok"])
        self.assertEqual(r["backend"], "windows_native")

    def test_unknown_action(self):
        r = maintenance.maintenance_tool({"action": "frobnicate"}, self.state)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")

    def test_disk_cleanup_describe_is_prose_not_executable(self):
        # T2-maintenance-disk-cleanup-cmd-list-027: jamás devolver arrays
        # ejecutables; solo prosa + needs_user (operación irreversible).
        r = maintenance.maintenance_tool({"action": "disk_cleanup_describe"}, self.state)
        self.assertTrue(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        self.assertFalse(r["verified"])
        # no debe haber ninguna lista de comandos ejecutables en la respuesta
        for v in r.values():
            self.assertNotIsInstance(v, list)


class TestDefenderStatus(unittest.TestCase):
    def test_success_parses_json(self):
        with patch.object(maintenance.subprocess, "run",
                          return_value=_proc(0, '{"AntivirusEnabled": true}')):
            r = maintenance._maintenance_defender_status()
        self.assertTrue(r["ok"])
        self.assertEqual(r["defender"], {"AntivirusEnabled": True})

    def test_failure_returncode(self):
        with patch.object(maintenance.subprocess, "run",
                          return_value=_proc(1, "", "access denied")):
            r = maintenance._maintenance_defender_status()
        self.assertFalse(r["ok"])

    def test_invalid_json_is_honest(self):
        with patch.object(maintenance.subprocess, "run",
                          return_value=_proc(0, "garbage{")):
            r = maintenance._maintenance_defender_status()
        self.assertFalse(r["ok"])
        self.assertIn("raw", r)


class TestFirewallStatus(unittest.TestCase):
    def test_single_profile_wrapped_in_list(self):
        with patch.object(maintenance.subprocess, "run",
                          return_value=_proc(0, '{"Name":"Domain","Enabled":true}')):
            r = maintenance._maintenance_firewall_status()
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 1)
        self.assertIsInstance(r["profiles"], list)

    def test_failure(self):
        with patch.object(maintenance.subprocess, "run", return_value=_proc(1, "", "err")):
            self.assertFalse(maintenance._maintenance_firewall_status()["ok"])


class TestWindowsUpdateStatus(unittest.TestCase):
    def test_timeout_does_not_propagate(self):
        # COM puede colgarse si wuauserv está detenido -> capturado como _err.
        with patch.object(maintenance.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired(cmd="ps", timeout=30)):
            r = maintenance._maintenance_windows_update_status()
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "wuauserv_unresponsive")

    def test_success_spreads_data(self):
        with patch.object(maintenance.subprocess, "run",
                          return_value=_proc(0, '{"last_install_success": "2026-01-01"}')):
            r = maintenance._maintenance_windows_update_status()
        self.assertTrue(r["ok"])
        self.assertEqual(r["last_install_success"], "2026-01-01")


class TestEventLogsInjectionGuard(unittest.TestCase):
    def test_bad_log_name_rejected_before_subprocess(self):
        # CC-100 / T2-maintenance-event-log-injection-025: log por allowlist.
        with patch.object(maintenance.subprocess, "run") as m:
            r = maintenance._maintenance_event_logs({"log": "System'; Stop-Computer #"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        self.assertFalse(m.called)

    def test_non_integer_hours_rejected(self):
        with patch.object(maintenance.subprocess, "run") as m:
            r = maintenance._maintenance_event_logs({"log": "System", "hours": "lots"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        self.assertFalse(m.called)

    def test_valid_query_parses_events(self):
        with patch.object(maintenance.subprocess, "run",
                          return_value=_proc(0, '[{"Id":1000},{"Id":1001}]')):
            r = maintenance._maintenance_event_logs({"log": "Application", "hours": 12})
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 2)
        self.assertEqual(r["log"], "Application")
        self.assertEqual(r["hours"], 12)

    def test_timeout_captured(self):
        with patch.object(maintenance.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired(cmd="ps", timeout=30)):
            r = maintenance._maintenance_event_logs({"log": "System"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "event_log_too_large")


class TestServiceStatus(unittest.TestCase):
    def test_missing_name(self):
        self.assertFalse(maintenance._maintenance_service_status({})["ok"])

    def test_service_not_found(self):
        with patch.object(maintenance.subprocess, "run", return_value=_proc(0, "")):
            r = maintenance._maintenance_service_status({"name": "Spooler"})
        self.assertFalse(r["ok"])

    def test_service_found(self):
        with patch.object(maintenance.subprocess, "run",
                          return_value=_proc(0, '{"Name":"Spooler","Status":4}')):
            r = maintenance._maintenance_service_status({"name": "Spooler"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["service"]["Name"], "Spooler")


class TestServiceControl(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="maint_svc_"))
        self.state = AgentState(self.tmp / "s.json")

    def test_missing_name(self):
        self.assertFalse(
            maintenance._maintenance_service_control("service_stop", {}, self.state)["ok"])

    def test_aborts_if_service_not_found(self):
        # before-status falla -> control debe abortar y devolver ese error.
        with patch.object(maintenance.subprocess, "run", return_value=_proc(0, "")):
            r = maintenance._maintenance_service_control(
                "service_stop", {"name": "NoSuchSvc"}, self.state)
        self.assertFalse(r["ok"])

    def test_control_success_creates_checkpoint_and_verifies(self):
        found = _proc(0, '{"Name":"Spooler","Status":4}')
        # secuencia: before status, control (rc=0), after status
        with patch.object(maintenance.subprocess, "run",
                          side_effect=[found, _proc(0, ""), found]):
            r = maintenance._maintenance_service_control(
                "service_stop", {"name": "Spooler"}, self.state)
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"])      # returncode 0 -> verified
        self.assertIn("checkpoint", r)       # rollback registrado
        # el checkpoint con rollback inverso quedó persistido
        self.assertEqual(len(self.state._load()["checkpoints"]), 1)

    def test_control_failure_does_not_claim_verified(self):
        # HONESTIDAD: si el Stop-Service falla (rc!=0), verified debe ser False.
        found = _proc(0, '{"Name":"Spooler","Status":4}')
        with patch.object(maintenance.subprocess, "run",
                          side_effect=[found, _proc(1, "", "denied"), found]):
            r = maintenance._maintenance_service_control(
                "service_stop", {"name": "Spooler"}, self.state)
        self.assertTrue(r["ok"])           # el tool corrió
        self.assertFalse(r["verified"])    # pero la mutación NO se verificó


class TestRestorePoint(unittest.TestCase):
    def test_failure_explains_system_restore(self):
        with patch.object(maintenance.subprocess, "run", return_value=_proc(1, "", "disabled")):
            r = maintenance._maintenance_restore_point_create({})
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        self.assertIn("System Restore", r["error"])

    def test_success(self):
        with patch.object(maintenance.subprocess, "run", return_value=_proc(0, "")):
            r = maintenance._maintenance_restore_point_create({"description": "before update"})
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"])
        self.assertEqual(r["description"], "before update")


if __name__ == "__main__":
    unittest.main()
