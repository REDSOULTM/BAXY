"""Cobertura dedicada para domain_tools/container.py (added 2026-06-01).

container.py NO tenía test propio (solo el smoke {action:status}). Envuelve
docker / docker-compose. Punto de seguridad: exec acepta una command LIST
explícita y corre `docker exec` por argv — NO envuelve shells arbitrarios, así
que no hay inyección de shell aunque el comando venga del modelo.

Todo subprocess (docker) y shutil.which se mockean — cero docker real.

Propiedades afirmadas contra el código fuente:
  - sin docker en PATH -> needs_dependency (no crash, install_hint)
  - status reporta presencia de docker honestamente
  - ps parsea las líneas {{json .}} (una por contenedor), ignora basura
  - exec corre por argv ([docker, exec, target, *cmd]) sin shell -> no inyectable
  - exec/lifecycle: verified refleja returncode real (honestidad)
  - lifecycle crea checkpoint con rollback inverso (start<->stop)
  - acción desconocida -> needs_user
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ..domain_tools import container
from ..memory_pkg.state import AgentState


def _proc(returncode=0, stdout="", stderr=""):
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


_DOCKER = "C:\\docker\\docker.exe"


class TestContainerStatusAndDependency(unittest.TestCase):
    def test_status_reports_docker_present(self):
        with patch.object(container.shutil, "which", return_value=_DOCKER):
            r = container.container_tool({"action": "status"}, None)
        self.assertTrue(r["ok"])
        self.assertTrue(r["docker"])

    def test_status_reports_docker_absent(self):
        with patch.object(container.shutil, "which", return_value=None):
            r = container.container_tool({"action": "status"}, None)
        self.assertTrue(r["ok"])
        self.assertFalse(r["docker"])

    def test_no_docker_returns_needs_dependency(self):
        with patch.object(container.shutil, "which", return_value=None):
            r = container.container_tool({"action": "ps"}, None)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_dependency")
        self.assertIn("install_hint", r)


class TestContainerPs(unittest.TestCase):
    def test_ps_parses_json_lines_and_skips_garbage(self):
        out = '{"ID":"abc","Names":"web"}\n\nnot-json\n{"ID":"def","Names":"db"}\n'
        with patch.object(container.shutil, "which", return_value=_DOCKER), \
             patch.object(container.subprocess, "run", return_value=_proc(0, out)):
            r = container.container_tool({"action": "ps"}, None)
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 2)
        self.assertEqual({c["Names"] for c in r["containers"]}, {"web", "db"})

    def test_ps_all_inserts_dash_a(self):
        with patch.object(container.shutil, "which", return_value=_DOCKER), \
             patch.object(container.subprocess, "run", return_value=_proc(0, "")) as m:
            container.container_tool({"action": "ps_all"}, None)
        argv = m.call_args.args[0]
        self.assertIn("-a", argv)

    def test_ps_failure_is_honest(self):
        with patch.object(container.shutil, "which", return_value=_DOCKER), \
             patch.object(container.subprocess, "run", return_value=_proc(1, "", "daemon down")):
            r = container.container_tool({"action": "ps"}, None)
        self.assertFalse(r["ok"])


class TestContainerExecNoShellInjection(unittest.TestCase):
    def test_exec_runs_by_argv_not_shell(self):
        # SEGURIDAD: el comando se pasa como argv a `docker exec`, NO via shell.
        # Un payload de inyección queda como argumentos literales inertes.
        with patch.object(container.shutil, "which", return_value=_DOCKER), \
             patch.object(container.subprocess, "run", return_value=_proc(0, "out")) as m:
            r = container.container_tool(
                {"action": "exec", "name": "web", "command": ["sh", "-c", "echo hi; rm -rf /"]},
                None,
            )
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"])
        argv = m.call_args.args[0]
        # forma exacta: [docker, exec, target, *cmd] — sin shell=True
        self.assertEqual(argv[:3], [_DOCKER, "exec", "web"])
        self.assertEqual(argv[3:], ["sh", "-c", "echo hi; rm -rf /"])
        self.assertNotIn("shell", m.call_args.kwargs)

    def test_exec_string_command_is_split(self):
        with patch.object(container.shutil, "which", return_value=_DOCKER), \
             patch.object(container.subprocess, "run", return_value=_proc(0)) as m:
            container.container_tool({"action": "exec", "name": "web", "command": "ls -la"}, None)
        argv = m.call_args.args[0]
        self.assertEqual(argv[3:], ["ls", "-la"])

    def test_exec_failure_returncode_not_verified(self):
        with patch.object(container.shutil, "which", return_value=_DOCKER), \
             patch.object(container.subprocess, "run", return_value=_proc(127, "", "not found")):
            r = container.container_tool({"action": "exec", "name": "web", "command": ["nope"]}, None)
        self.assertFalse(r["verified"])  # returncode != 0

    def test_exec_missing_target_or_command(self):
        with patch.object(container.shutil, "which", return_value=_DOCKER):
            self.assertFalse(container.container_tool({"action": "exec", "command": ["ls"]}, None)["ok"])
            self.assertFalse(container.container_tool({"action": "exec", "name": "web"}, None)["ok"])
            self.assertFalse(container.container_tool({"action": "exec", "name": "web", "command": []}, None)["ok"])


class TestContainerLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ct_life_"))
        self.state = AgentState(self.tmp / "s.json")

    def test_stop_creates_checkpoint_with_inverse_rollback(self):
        before = self.state.list_checkpoints()["count"]
        with patch.object(container.shutil, "which", return_value=_DOCKER), \
             patch.object(container.subprocess, "run", return_value=_proc(0, "web")):
            r = container.container_tool({"action": "stop", "name": "web"}, self.state)
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"])
        self.assertEqual(self.state.list_checkpoints()["count"], before + 1)
        # el rollback de un stop es un start
        chk = self.state.list_checkpoints()["checkpoints"][-1]
        self.assertEqual(chk["rollback"][0]["args"]["action"], "start")

    def test_lifecycle_failure_not_verified(self):
        with patch.object(container.shutil, "which", return_value=_DOCKER), \
             patch.object(container.subprocess, "run", return_value=_proc(1, "", "no such container")):
            r = container.container_tool({"action": "start", "name": "ghost"}, self.state)
        self.assertFalse(r["verified"])

    def test_lifecycle_missing_target(self):
        with patch.object(container.shutil, "which", return_value=_DOCKER):
            r = container.container_tool({"action": "stop"}, self.state)
        self.assertFalse(r["ok"])


class TestContainerUnknownAction(unittest.TestCase):
    def test_unknown_action_needs_user(self):
        with patch.object(container.shutil, "which", return_value=_DOCKER):
            r = container.container_tool({"action": "self_destruct"}, None)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")


if __name__ == "__main__":
    unittest.main()
