"""Cobertura dedicada para domain_tools/network.py (added 2026-06-01).

network.py NO tenía test propio: el único ejercicio era el smoke
`{action:status}` de test_r4_all_handlers_smoke.py. Este archivo cubre
los caminos REALES de cada acción de diagnóstico de red, con TODO subprocess
y red mockeados (CLAUDE.md: nada de efectos físicos / red real en tests).

Cada test afirma una propiedad verificada contra el código fuente:
  - honestidad: reachable/verified reflejan returncode, no se inventan
  - guardas de inyección: state filter y DNS IPs por allowlist
  - delegación wifi-connect (el modelo chico rutea "conectá a X" a network)
  - manejo de errores: returncode!=0 -> ok:False; JSON inválido -> ok:False

Todos los subprocess.run se patchean a nivel del módulo network.subprocess,
que es el mismo objeto-módulo que helpers.subprocess (verificado: comparten
la referencia), así que un patch alcanza ambos caminos.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ..domain_tools import network
from ..memory_pkg.state import AgentState


def _proc(returncode=0, stdout="", stderr=""):
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


class TestNetworkStatus(unittest.TestCase):
    def test_status_reports_tooling(self):
        r = network.network_tool({"action": "status"}, None)
        self.assertTrue(r["ok"])
        # status no debe mentir: anuncia el backend y que dns_set necesita el adapter
        self.assertEqual(r["backend"], "windows_net")
        self.assertIn("powershell", r)
        self.assertIn("dns_set", r["note"])

    def test_unknown_action_is_needs_user_not_crash(self):
        r = network.network_tool({"action": "no_such_action"}, None)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        self.assertEqual(r["action"], "no_such_action")


class TestNetworkPing(unittest.TestCase):
    def test_ping_missing_host(self):
        self.assertFalse(network._network_ping({})["ok"])

    def test_ping_reachable_reflects_returncode_zero(self):
        with patch.object(network.subprocess, "run", return_value=_proc(0, "Reply from 8.8.8.8")) as m:
            r = network._network_ping({"host": "8.8.8.8", "count": 2})
        self.assertTrue(r["ok"])
        self.assertTrue(r["reachable"])          # returncode 0 -> reachable
        self.assertEqual(r["host"], "8.8.8.8")
        self.assertEqual(r["count"], 2)
        # el comando es el ping nativo con -n <count> <host> (no inyectable: argv)
        argv = m.call_args.args[0]
        self.assertEqual(argv[:2], ["ping", "-n"])
        self.assertEqual(argv[-1], "8.8.8.8")

    def test_ping_unreachable_does_not_claim_success(self):
        # HONESTIDAD: returncode!=0 NO debe dar reachable=True
        with patch.object(network.subprocess, "run", return_value=_proc(1, "", "timed out")):
            r = network._network_ping({"host": "bad.invalid"})
        self.assertTrue(r["ok"])               # el tool corrió bien
        self.assertFalse(r["reachable"])       # pero el host NO respondió


class TestNetworkPortCheck(unittest.TestCase):
    def test_port_check_missing_args(self):
        self.assertFalse(network._network_port_check({"host": "x"})["ok"])  # falta port
        self.assertFalse(network._network_port_check({"port": 80})["ok"])   # falta host

    def test_port_check_reachable_parses_true(self):
        with patch.object(network.subprocess, "run", return_value=_proc(0, "True\n")):
            r = network._network_port_check({"host": "example.com", "port": 443})
        self.assertTrue(r["reachable"])
        self.assertEqual(r["port"], 443)

    def test_port_check_closed_parses_false(self):
        with patch.object(network.subprocess, "run", return_value=_proc(0, "False")):
            r = network._network_port_check({"host": "example.com", "port": 1})
        self.assertFalse(r["reachable"])


class TestNetworkConnectionsAllowlist(unittest.TestCase):
    def test_bad_state_filter_rejected_before_subprocess(self):
        # CC-100: el state filter va por allowlist RX_TCP_STATE; un valor con
        # inyección debe rechazarse SIN ejecutar PowerShell.
        with patch.object(network.subprocess, "run") as m:
            r = network._network_connections({"state": "Established; Stop-Computer"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        self.assertFalse(m.called)  # nunca llegó a PowerShell

    def test_valid_state_filter_parses_json_list(self):
        with patch.object(network.subprocess, "run", return_value=_proc(0, '[{"LocalPort":443}]')):
            r = network._network_connections({"state": "Established"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["state"], "Established")

    def test_connections_failure_returncode(self):
        with patch.object(network.subprocess, "run", return_value=_proc(1, "", "denied")):
            r = network._network_connections({"state": "Established"})
        self.assertFalse(r["ok"])

    def test_connections_empty_output_is_empty_list(self):
        with patch.object(network.subprocess, "run", return_value=_proc(0, "")):
            r = network._network_connections({"state": "Listen"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 0)
        self.assertEqual(r["connections"], [])


class TestNetworkDnsResolve(unittest.TestCase):
    def test_missing_name(self):
        self.assertFalse(network._network_dns_resolve({})["ok"])

    def test_resolve_single_record_wrapped_in_list(self):
        with patch.object(network.subprocess, "run", return_value=_proc(0, '{"Name":"x","IPAddress":"1.2.3.4"}')):
            r = network._network_dns_resolve({"name": "example.com"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 1)
        self.assertIsInstance(r["records"], list)

    def test_resolve_invalid_json(self):
        with patch.object(network.subprocess, "run", return_value=_proc(0, "not json{")):
            r = network._network_dns_resolve({"name": "example.com"})
        self.assertFalse(r["ok"])
        self.assertIn("raw", r)


class TestNetworkDnsGet(unittest.TestCase):
    def test_dns_get_failure(self):
        with patch.object(network.subprocess, "run", return_value=_proc(1, "", "err")):
            r = network._network_dns_get({})
        self.assertFalse(r["ok"])

    def test_dns_get_empty_is_zero(self):
        with patch.object(network.subprocess, "run", return_value=_proc(0, "")):
            r = network._network_dns_get({})
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 0)


class TestNetworkDnsSetInjectionGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="net_dns_"))
        self.state = AgentState(self.tmp / "s.json")

    def test_missing_adapter(self):
        self.assertFalse(network._network_dns_set({"addresses": ["8.8.8.8"]}, self.state)["ok"])

    def test_missing_addresses(self):
        self.assertFalse(network._network_dns_set({"adapter": "Ethernet"}, self.state)["ok"])

    def test_invalid_ip_refused_and_set_command_never_runs(self):
        # CC-100 / T2-network-dns-set-injection-033: una IP inválida (potencial
        # inyección) debe rechazarse con needs_user. Lo CRÍTICO es que el comando
        # destructivo Set-DnsClientServerAddress NUNCA se ejecute.
        # NOTA (no-bug, observado al testear): _network_dns_set toma el snapshot
        # 'before' (1 subprocess dns_get) y crea un checkpoint ANTES de validar
        # las IPs, así que sí hay un read+state-write previo al rechazo; pero la
        # escritura peligrosa queda correctamente bloqueada.
        calls = []

        def fake_run(argv, *a, **k):
            calls.append(argv)
            return _proc(0, "")  # dns_get (before) devuelve vacío -> serializable

        with patch.object(network.subprocess, "run", side_effect=fake_run):
            r = network._network_dns_set(
                {"adapter": "Ethernet", "addresses": ["169.254.0.1; rm -rf /"]},
                self.state,
            )
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        # ningún comando ejecutado debe contener Set-DnsClientServerAddress
        joined = " ".join(" ".join(str(p) for p in c) for c in calls)
        self.assertNotIn("Set-DnsClientServerAddress", joined)


class TestNetworkPublicIp(unittest.TestCase):
    def test_public_ip_success(self):
        cm = MagicMock()
        cm.read.return_value = b"203.0.113.7\n"
        with patch("urllib.request.urlopen") as uo:
            uo.return_value.__enter__.return_value = cm
            r = network._network_public_ip()
        self.assertTrue(r["ok"])
        self.assertEqual(r["ip"], "203.0.113.7")  # stripped
        self.assertTrue(r["verified"])

    def test_public_ip_network_failure_is_honest(self):
        with patch("urllib.request.urlopen", side_effect=OSError("no route")):
            r = network._network_public_ip()
        self.assertFalse(r["ok"])
        self.assertIn("error", r)


class TestNetworkWifiDelegation(unittest.TestCase):
    """El modelo chico a veces rutea "conectá a la red X" a network en vez de
    device_settings. network_tool delega a _device_wifi_connect en vez de
    fallar (network.py:78-85)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="net_wifi_"))
        self.state = AgentState(self.tmp / "s.json")

    def test_connect_action_delegates(self):
        with patch("gemma4_agent.domain_tools.wifi._device_wifi_connect") as wc:
            wc.return_value = {"ok": True, "connected": True}
            r = network.network_tool({"action": "connect", "name": "Home"}, self.state)
        self.assertTrue(wc.called)
        self.assertEqual(r["delegated_from"], "network.connect")

    def test_name_with_status_action_delegates(self):
        # `network {name:'RV'}` sin action explícita también debe resolverse a wifi
        with patch("gemma4_agent.domain_tools.wifi._device_wifi_connect") as wc:
            wc.return_value = {"ok": True}
            r = network.network_tool({"action": "status", "name": "RV"}, self.state)
        self.assertTrue(wc.called)
        self.assertEqual(r["delegated_from"], "network.status")

    def test_plain_status_does_not_delegate(self):
        with patch("gemma4_agent.domain_tools.wifi._device_wifi_connect") as wc:
            r = network.network_tool({"action": "status"}, self.state)
        self.assertFalse(wc.called)
        self.assertTrue(r["ok"])


class TestNetworkFirewallNotExposed(unittest.TestCase):
    def test_firewall_mutations_refused(self):
        for action in ("firewall_allow", "firewall_block", "firewall_remove"):
            r = network.network_tool({"action": action}, None)
            self.assertFalse(r["ok"], action)
            self.assertEqual(r["status"], "needs_user", action)


if __name__ == "__main__":
    unittest.main()
