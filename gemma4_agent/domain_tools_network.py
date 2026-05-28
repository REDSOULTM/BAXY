"""Network diagnostics domain tool — extracted from domain_tools.py
(R2 sprint 2026-05-28).

ping/traceroute/dns_get/dns_set/dns_resolve/port_check/connections/public_ip.
PS-injection protection (CC-100 / T2-network-dns-set-injection-033): adapter
y addresses van por env-var, allowlists para IP/state filter.

DELEGACIÓN wifi-connect (2026-05-27): el modelo chico a veces rutea "conectá
a la red X" a network (diagnóstico) en vez de device_settings; en vez de
fallar/ignorar, network_tool delega a _device_wifi_connect cuando ve intent
de UNIRSE a una red.

Funciones extraídas (9):
  network_tool                    (entry, 9 acciones)
  _network_ping
  _network_traceroute
  _network_dns_get
  _network_dns_set                (con rollback snapshot)
  _network_dns_resolve
  _network_port_check
  _network_connections
  _network_public_ip

Helpers desde domain_tools (lazy):
  _ps_quote, parse_ps_json (vía ._ps), _device_wifi_connect (vía
  .domain_tools_wifi)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

from ._ps import (
    PSValidationError,
    RX_TCP_STATE,
    is_ipv4,
    is_ipv6,
    parse_ps_json,
    ps_safe_literal,
)
from ._shared import _err, _ok
from .tool_result import ToolResult
from .state import AgentState


__all__ = [
    "network_tool",
    "_network_ping",
    "_network_traceroute",
    "_network_dns_get",
    "_network_dns_set",
    "_network_dns_resolve",
    "_network_port_check",
    "_network_connections",
    "_network_public_ip",
]


# R4 sprint 2026-05-28: handler migrado a ToolResult con .to_dict().
def _ok_tr(**kw):
    return ToolResult.ok_result(**kw).to_dict()


def _err_tr(msg, **kw):
    return ToolResult.err(msg, **kw).to_dict()


def network_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for network diagnostics.

    Actions: status, ping(host), traceroute(host), dns_get, dns_set(adapter,
    addresses, snapshot=True), dns_resolve(name), port_check(host, port),
    connections, public_ip. Writing actions (dns_set) snapshot the previous
    config so they can be rolled back via state.rollback.
    """
    from .domain_tools_wifi import _device_wifi_connect
    action = str(args.get("action") or "status").casefold()
    # DELEGACIÓN wifi-connect (2026-05-27): el modelo chico a veces rutea
    # "conectá a la red X" a `network` (diagnóstico) en vez de device_settings
    # (que tiene wifi_connect). En vez de fallar/ignorar — que deja al usuario sin
    # manos sin conexión — garantizamos la precondición delegando a la conexión
    # WiFi real (mismo patrón que browser.open->app.open). Detecta intención de
    # UNIRSE a una red: acción connect/join/wifi*, o un name/ssid presente (lo que
    # el modelo nunca manda para un ping/dns). Va ANTES del status default para
    # que `network {name: 'RV'}` (sin action) también se resuelva.
    _connectish = action in {
        "connect", "wifi_connect", "join", "wifi", "wifi_join", "connect_wifi"}
    _has_target = bool(str(args.get("name") or args.get("ssid") or "").strip())
    if _connectish or (_has_target and action in {"", "status"}):
        res = _device_wifi_connect(args)
        if isinstance(res, dict):
            res.setdefault("delegated_from", "network." + (action or "connect"))
        return res
    if action == "status":
        return _ok_tr(
            powershell=bool(shutil.which("powershell")),
            ping=bool(shutil.which("ping")),
            tracert=bool(shutil.which("tracert")),
            backend="windows_net",
            note="dns_set requires the adapter name from dns_get and snapshots the previous list.",
        )
    if action == "ping":
        return _network_ping(args)
    if action == "traceroute":
        return _network_traceroute(args)
    if action == "dns_get":
        return _network_dns_get(args)
    if action == "dns_set":
        return _network_dns_set(args, state)
    if action in {"dns_resolve", "resolve"}:
        return _network_dns_resolve(args)
    if action == "port_check":
        return _network_port_check(args)
    if action == "connections":
        return _network_connections(args)
    if action == "public_ip":
        return _network_public_ip()
    if action in {"firewall_allow", "firewall_block", "firewall_remove"}:
        return _err_tr(
            f"network.{action} is intentionally not exposed; modifying firewall rules requires explicit terminal commands",
            status="needs_user",
        )
    return _err_tr(
        "unknown network action", action=action,
        valid_actions=[
            "status", "ping", "traceroute", "dns_get", "dns_set",
            "dns_lookup", "speedtest", "wifi_info", "active_connections",
        ],
        status="needs_user",
    )


def _network_ping(args: dict[str, Any]) -> dict[str, Any]:
    host = str(args.get("host") or args.get("target") or "").strip()
    if not host:
        return _err_tr("missing host")
    count = int(args.get("count", 4))
    proc = subprocess.run(["ping", "-n", str(count), host], capture_output=True, text=True, timeout=30)
    return _ok_tr(host=host, count=count, exit_code=proc.returncode, stdout=proc.stdout[-3000:], reachable=proc.returncode == 0)


def _network_traceroute(args: dict[str, Any]) -> dict[str, Any]:
    host = str(args.get("host") or args.get("target") or "").strip()
    if not host:
        return _err_tr("missing host")
    max_hops = int(args.get("max_hops", 20))
    proc = subprocess.run(["tracert", "-h", str(max_hops), host], capture_output=True, text=True, timeout=120)
    return _ok_tr(host=host, max_hops=max_hops, exit_code=proc.returncode, stdout=proc.stdout[-4000:])


def _network_dns_get(args: dict[str, Any]) -> dict[str, Any]:
    from .domain_tools_helpers import _ps_quote
    adapter = str(args.get("adapter") or "").strip()
    cmd = "Get-DnsClientServerAddress | Where-Object { $_.ServerAddresses } | Select-Object InterfaceAlias,AddressFamily,ServerAddresses | ConvertTo-Json -Depth 3"
    if adapter:
        cmd = f"Get-DnsClientServerAddress -InterfaceAlias '{_ps_quote(adapter)}' | Select-Object InterfaceAlias,AddressFamily,ServerAddresses | ConvertTo-Json -Depth 3"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=15)
    if proc.returncode != 0:
        return _err_tr("dns_get failed", stderr=proc.stderr)
    raw = proc.stdout.strip()
    if not raw:
        return _ok_tr(adapters=[], count=0)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err_tr("dns_get invalid JSON", raw=raw[:500])
    if isinstance(data, dict):
        data = [data]
    return _ok_tr(adapters=data, count=len(data))


def _network_dns_set(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    adapter = str(args.get("adapter") or "").strip()
    if not adapter:
        return _err_tr("missing adapter (use dns_get first)")
    addresses = args.get("addresses") if isinstance(args.get("addresses"), list) else None
    if not addresses:
        return _err_tr("missing addresses (list of DNS server IPs)")
    addresses = [str(a) for a in addresses if str(a).strip()]
    before = _network_dns_get({"adapter": adapter})
    rollback_addrs: list[str] = []
    for adapter_info in before.get("adapters", []):
        if str(adapter_info.get("InterfaceAlias", "")).casefold() == adapter.casefold() and adapter_info.get("AddressFamily") == 2:
            rollback_addrs = adapter_info.get("ServerAddresses") or []
            break
    rollback_step = {"tool": "network", "args": {"action": "dns_set", "adapter": adapter, "addresses": rollback_addrs or ["AUTO"]}}
    checkpoint = state.checkpoint(
        f"dns_set {adapter}",
        rollback=[rollback_step] if rollback_addrs else [],
        metadata={"before": before, "target_addresses": addresses},
    )
    # CC-100 / T2-network-dns-set-injection-033: validar cada IP antes de
    # interpolar; adapter va por env-var; addresses van también via env-var
    # como string separado por comas.
    if addresses == ["AUTO"] or addresses == ["auto"]:
        env = {**os.environ, "GEMMA4_DNS_ADAPTER": adapter}
        cmd = "Set-DnsClientServerAddress -InterfaceAlias $env:GEMMA4_DNS_ADAPTER -ResetServerAddresses"
    else:
        for addr in addresses:
            if not (is_ipv4(addr) or is_ipv6(addr)):
                return _err_tr(f"invalid DNS address: {addr!r}", status="needs_user")
        env = {
            **os.environ,
            "GEMMA4_DNS_ADAPTER": adapter,
            "GEMMA4_DNS_ADDRS": ",".join(addresses),
        }
        cmd = (
            "$addrs = $env:GEMMA4_DNS_ADDRS -split ','; "
            "Set-DnsClientServerAddress -InterfaceAlias $env:GEMMA4_DNS_ADAPTER -ServerAddresses $addrs"
        )
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], env=env, capture_output=True, text=True, timeout=15)
    after = _network_dns_get({"adapter": adapter})
    return _ok_tr(
        adapter=adapter, target=addresses, before=rollback_addrs, after=after,
        exit_code=proc.returncode, stderr=proc.stderr[-1000:],
        checkpoint=checkpoint.get("checkpoint"),
        verified=proc.returncode == 0,
    )


def _network_dns_resolve(args: dict[str, Any]) -> dict[str, Any]:
    from .domain_tools_helpers import _ps_quote
    name = str(args.get("name") or args.get("host") or "").strip()
    if not name:
        return _err_tr("missing name")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Resolve-DnsName '{_ps_quote(name)}' -ErrorAction SilentlyContinue | Select-Object Name,Type,IPAddress,NameHost,TTL | ConvertTo-Json -Depth 3"],
        capture_output=True, text=True, timeout=15,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        return _err_tr("dns_resolve failed", stderr=proc.stderr, name=name)
    raw = proc.stdout.strip()
    if not raw:
        return _ok_tr(name=name, records=[], count=0)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err_tr("dns_resolve invalid JSON", raw=raw[:500])
    if isinstance(data, dict):
        data = [data]
    return _ok_tr(name=name, records=data, count=len(data))


def _network_port_check(args: dict[str, Any]) -> dict[str, Any]:
    from .domain_tools_helpers import _ps_quote
    host = str(args.get("host") or args.get("target") or "").strip()
    port = args.get("port")
    if not host or port is None:
        return _err_tr("missing host or port")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Test-NetConnection -ComputerName '{_ps_quote(host)}' -Port {int(port)} -InformationLevel Quiet -WarningAction SilentlyContinue"],
        capture_output=True, text=True, timeout=20,
    )
    reachable = (proc.stdout or "").strip().casefold() == "true"
    return _ok_tr(host=host, port=int(port), reachable=reachable, exit_code=proc.returncode)


def _network_connections(args: dict[str, Any]) -> dict[str, Any]:
    # CC-100 / T2-network-connections-state-no-allowlist-034: enum allowlist.
    state_filter_raw = str(args.get("state") or "Established").strip()
    try:
        state_filter = ps_safe_literal(state_filter_raw, RX_TCP_STATE)
    except PSValidationError as exc:
        return _err_tr(f"invalid state filter: {exc}", status="needs_user")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Get-NetTCPConnection -State {state_filter} -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess | ConvertTo-Json -Depth 3"],
        capture_output=True, text=True, timeout=20,
    )
    if proc.returncode != 0:
        return _err_tr("connections query failed", stderr=proc.stderr)
    ok_parse, data = parse_ps_json(proc.stdout)
    if not ok_parse:
        return _err_tr("connections invalid JSON", raw=data)
    if data is None:
        return _ok_tr(connections=[], count=0, state=state_filter)
    if isinstance(data, dict):
        data = [data]
    return _ok_tr(connections=data, count=len(data), state=state_filter)


def _network_public_ip() -> dict[str, Any]:
    import urllib.request
    try:
        req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "Gemma4Agent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return _ok_tr(ip=resp.read().decode("utf-8").strip(), source="api.ipify.org", verified=True)
    except Exception as exc:
        return _err_tr(f"public_ip failed: {exc}")
