"""Harness con stubs aislados para Modo A de la smoke battery 50/50.

Provee un context manager `smoke_env()` que:
  - Crea state/captures en un tempdir bajo `audit/smoke_workspace/`.
  - Monkeypatcha subprocess.run/Popen, os.startfile, urllib.request.urlopen,
    socket.getaddrinfo, playwright y otros side-effects para que las tools
    NO toquen la máquina del usuario.
  - Devuelve un `ToolRegistry` listo para `.execute(...)`.

Uso:
    with smoke_env(safety_enabled=True) as ctx:
        out = ctx.registry.execute("system", {"action": "time"})
        ctx.assert_no_real_subprocess()  # opcional
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Fakes para subprocess y otros side-effects
# ---------------------------------------------------------------------------


@dataclass
class FakeProc:
    args: Any
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    pid: int = 12345

    def communicate(self, input: Any = None, timeout: Any = None):
        return self.stdout, self.stderr


class _SubprocessRecorder:
    """Registra todas las invocaciones a subprocess.run / Popen y devuelve
    respuestas canned según patrones en argv."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.popen_calls: list[dict[str, Any]] = []

    def _match(self, argv: Any) -> tuple[int, str, str]:
        """Devuelve (returncode, stdout, stderr) para una invocación."""
        s = " ".join(str(p) for p in argv) if isinstance(argv, (list, tuple)) else str(argv)
        low = s.casefold()
        # PowerShell / Get-CimInstance: devolvemos JSON razonable
        if "powershell" in low:
            if "win32_processor" in low or "win32_videocontroller" in low or "cpu_ram_gpu" in low.replace("$", ""):
                return 0, json.dumps({
                    "cpu": {"Name": "FakeCPU", "LoadPercentage": 12},
                    "os": {"TotalVisibleMemorySize": 16_000_000, "FreePhysicalMemory": 8_000_000},
                    "gpu": {"Name": "FakeGPU", "AdapterRAM": 8_000_000_000, "DriverVersion": "1.0"},
                }), ""
            if "win32_logicaldisk" in low:
                return 0, json.dumps([{"DeviceID": "C:", "DriveType": 3, "Size": 500_000_000_000, "FreeSpace": 200_000_000_000, "VolumeName": "OS"}]), ""
            if "win32_battery" in low:
                return 0, json.dumps({"Name": "FakeBattery", "EstimatedChargeRemaining": 75, "BatteryStatus": 2}), ""
            if "wmimonitorbrightness" in low:
                return 0, json.dumps({"CurrentBrightness": 80}), ""
            if "wmisetbrightness" in low:
                return 0, "", ""
            if "convertto-json" in low and "select-object" in low and "mainwindowtitle" in low:
                # list_windows
                return 0, json.dumps([{"ProcessName": "explorer", "MainWindowTitle": "File Explorer", "Id": 9999}]), ""
            if "get-foregroundwindow" in low or ("$h=" in low and "win32" in low):
                # window_active
                return 0, json.dumps({"hwnd": 1, "title": "FakeWindow", "pid": 9999, "process": "explorer"}), ""
            if "[system.windows.forms.sendkeys]" in low:
                return 0, "", ""
            if "get-clipboard" in low:
                return 0, "clipboard content", ""
            if "set-clipboard" in low:
                return 0, "", ""
            if "get-winevent" in low or "filterhashtable" in low:
                return 0, json.dumps([{"TimeCreated": "2026-05-15T00:00:00", "Id": 1000, "LevelDisplayName": "Information", "ProviderName": "Test", "Message": "fake"}]), ""
            if "get-service" in low:
                return 0, json.dumps([{"Name": "Spooler", "DisplayName": "Print Spooler", "Status": 4, "StartType": 2}]), ""
            if "get-pnpdevice" in low:
                return 0, json.dumps([{"FriendlyName": "Speakers", "Status": "OK", "InstanceId": "FAKE\\1"}]), ""
            if "get-dnsclient" in low or "resolve-dnsname" in low:
                return 0, json.dumps([{"Name": "example.com", "IPAddress": "93.184.216.34", "Type": 1, "TTL": 3600}]), ""
            if "test-netconnection" in low:
                return 0, "True", ""
            if "get-nettcpconnection" in low:
                return 0, json.dumps([{"LocalAddress": "127.0.0.1", "LocalPort": 80, "RemoteAddress": "10.0.0.1", "RemotePort": 443, "State": "Established", "OwningProcess": 1}]), ""
            if "get-netfirewallprofile" in low:
                return 0, json.dumps([{"Name": "Domain", "Enabled": True, "DefaultInboundAction": "Block", "DefaultOutboundAction": "Allow"}]), ""
            if "register-scheduledtask" in low:
                return 0, "", ""
            if "unregister-scheduledtask" in low:
                return 0, "", ""
            if "get-scheduledtask" in low:
                return 0, json.dumps({"State": "Ready", "LastRunTime": "2026-05-14T00:00:00", "NextRunTime": "2026-05-16T00:00:00", "LastTaskResult": 0, "NumberOfMissedRuns": 0}), ""
            if "set-dnsclientserveraddress" in low:
                return 0, "", ""
            if "uiautomationclient" in low or "$action" in low and "uia" in low.replace("_", "").replace("/", ""):
                return 0, json.dumps({"ok": True, "action": "find", "matches": [{"name": "OK", "control_type": "Button"}]}), ""
            if "copyfromscreen" in low or "system.drawing.bitmap" in low:
                # gui_screenshot
                # Honra GEMMA4_SCREENSHOT_PATH si vino por env (lo dejamos al recorder).
                screenshot_path = "fake_screenshot.png"
                # Inspect env via the caller — el recorder no tiene env, así que devolvemos placeholder.
                return 0, json.dumps({"path": screenshot_path, "width": 1920, "height": 1080, "left": 0, "top": 0, "mode": "all"}), ""
            if "[gemmamouse]" in low or "setcursorpos" in low:
                return 0, "", ""
            if "[win32]::movewindow" in low.replace(" ", ""):
                return 0, json.dumps({"ok": True, "title": "FakeWindow"}), ""
            if "messagebox" in low:
                return 0, "", ""
            if "start-mpscan" in low:
                return 0, "", ""
            if "checkpoint-computer" in low:
                return 0, "", ""
            if "get-mpcomputerstatus" in low:
                return 0, json.dumps({"AntivirusEnabled": True, "RealTimeProtectionEnabled": True}), ""
            if "get-process" in low and ("processname" in low or "select-object" in low):
                # PID owned check
                return 0, "FakeExe", ""
            if "get-itemproperty" in low or "test-path" in low:
                return 0, json.dumps({"InstallLocation": "C:\\FakeApp"}), ""
            if "get-filehash" in low:
                return 0, json.dumps({"Hash": "abc123def456" * 4, "Path": "fake", "Algorithm": "SHA256"}), ""
            if "get-authenticodesignature" in low:
                return 0, json.dumps({"Status": "Valid", "StatusMessage": "Signature valid", "SignerCertificate": {"Subject": "CN=Fake Inc"}, "Path": "fake"}), ""
            if "invoke-webrequest" in low:
                return 0, "", ""
            if "wia.devicemanager" in low.replace(".", ""):
                return 0, json.dumps([]), ""
            return 0, "", ""
        # reg.exe
        if argv and isinstance(argv, (list, tuple)) and str(argv[0]).lower().endswith("reg"):
            if "query" in [str(a).lower() for a in argv]:
                return 1, "", "ERROR: not found"  # default: no existe
            return 0, "", ""
        # tasklist
        if argv and isinstance(argv, (list, tuple)) and str(argv[0]).lower().endswith("tasklist"):
            return 0, '"explorer.exe","9999","Console","1","100,000 K"\n"chrome.exe","1234","Console","1","500,000 K"\n', ""
        # taskkill
        if argv and isinstance(argv, (list, tuple)) and str(argv[0]).lower().endswith("taskkill"):
            return 0, "SUCCESS: ...", ""
        # winget
        if "winget" in low:
            return 0, "Fake winget output", ""
        # shutdown
        if argv and isinstance(argv, (list, tuple)) and "shutdown" in str(argv[0]).lower():
            return 0, "", ""
        # rundll32 (sleep)
        if argv and isinstance(argv, (list, tuple)) and "rundll32" in str(argv[0]).lower():
            return 0, "", ""
        # ffmpeg
        if "ffmpeg" in low:
            return 0, "", ""
        # tesseract
        if "tesseract" in low:
            return 0, "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t1\t10\t20\t50\t30\t95\tOK\n5\t1\t1\t1\t1\t2\t70\t20\t40\t30\t90\tCancel\n", ""
        # git
        if argv and isinstance(argv, (list, tuple)) and str(argv[0]).lower().endswith("git"):
            return 0, "fake git output", ""
        return 0, "", ""

    def run(self, *args, **kwargs) -> FakeProc:
        argv = args[0] if args else kwargs.get("args")
        env = kwargs.get("env")
        record = {"argv": argv, "cwd": kwargs.get("cwd"), "shell": kwargs.get("shell"), "env_keys": sorted(list((env or {}).keys()))[:30] if env else None}
        rc, stdout, stderr = self._match(argv)
        # Para gui_screenshot, honra GEMMA4_SCREENSHOT_PATH si está en env y crea el archivo placeholder.
        if env and "GEMMA4_SCREENSHOT_PATH" in env:
            path = env["GEMMA4_SCREENSHOT_PATH"]
            try:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                # PNG mínimo 1x1
                Path(path).write_bytes(
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
                    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfa\xcf\x00\x00\x00"
                    b"\x02\x00\x01\xe5'\xde\xfc\x00\x00\x00\x00IEND\xaeB`\x82"
                )
                stdout = json.dumps({"path": path, "width": 1920, "height": 1080, "left": 0, "top": 0, "mode": env.get("GEMMA4_SCREENSHOT_MODE", "all")})
            except OSError:
                pass
        record["returncode"] = rc
        self.calls.append(record)
        return FakeProc(args=argv, returncode=rc, stdout=stdout, stderr=stderr)

    def popen(self, *args, **kwargs) -> FakeProc:
        argv = args[0] if args else kwargs.get("args")
        self.popen_calls.append({"argv": argv, "cwd": kwargs.get("cwd")})
        # Si pasaron stdout=open(file), escribimos algo y cerramos para no romper.
        stdout = kwargs.get("stdout")
        if hasattr(stdout, "write"):
            try:
                stdout.write(b"fake popen output\n" if "b" in getattr(stdout, "mode", "w") else "fake popen output\n")
            except (TypeError, ValueError, OSError):
                pass
        return FakeProc(args=argv, returncode=0, stdout="", stderr="", pid=22222)


class _UrllibRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def open(self, req, timeout: float = 30, *args, **kwargs):
        url = req.get_full_url() if hasattr(req, "get_full_url") else str(req)
        self.calls.append({"url": url, "timeout": timeout})
        host_low = url.lower()
        # Si apunta a private/loopback, _is_private_host del propio código debería detectarlo
        # antes de llegar aquí. Si llega: el guard del repo lo bloquearía con _SSRFGuardRedirectHandler.
        # Devolvemos respuesta HTML genérica.
        body = b"<html><head><title>FakeTitle</title></head><body>Fake page body for smoke test.</body></html>"
        return _FakeResponse(url, 200, body, headers={"content-type": "text/html; charset=utf-8"})


class _FakeResponse:
    def __init__(self, url: str, status: int, body: bytes, headers: dict[str, str]):
        self._url = url
        self.status = status
        self._body = body
        self.headers = _FakeHeaders(headers)

    def read(self, max_bytes: int | None = None) -> bytes:
        return self._body if max_bytes is None else self._body[:max_bytes]

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeHeaders:
    def __init__(self, data: dict[str, str]):
        self._d = {k.lower(): v for k, v in data.items()}

    def get(self, key: str, default: Any = None) -> Any:
        return self._d.get(key.lower(), default)


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


@dataclass
class SmokeContext:
    workspace: Path
    registry: Any  # ToolRegistry
    state: Any
    subprocess_rec: _SubprocessRecorder
    urllib_rec: _UrllibRecorder
    extras: dict[str, Any] = field(default_factory=dict)

    def assert_no_real_powershell_destructive(self) -> list[str]:
        """Reglas defensivas: ninguna invocación a powershell debe contener
        comandos catastróficos. Devuelve lista de hits."""
        bad = ("stop-computer", "restart-computer", "format ", "diskpart", "rd /s", "rmdir /s", "remove-item -recurse")
        hits = []
        for c in self.subprocess_rec.calls + self.subprocess_rec.popen_calls:
            argv = c.get("argv")
            s = " ".join(str(p) for p in argv) if isinstance(argv, (list, tuple)) else str(argv)
            low = s.casefold()
            for b in bad:
                if b in low:
                    hits.append(f"{b} :: {s[:200]}")
        return hits


@contextlib.contextmanager
def smoke_env(safety_enabled: bool = True):
    """Crea un entorno aislado con stubs activos. Limpia tempdir al salir."""
    from gemma4_agent.memory import MemoryStore
    from gemma4_agent.state import AgentState
    from gemma4_agent.tools import ToolRegistry

    workspace = Path(tempfile.mkdtemp(prefix="smoke_", dir=str(REPO_ROOT / "audit" / "smoke_workspace")))
    rec = _SubprocessRecorder()
    url_rec = _UrllibRecorder()

    def fake_startfile(path):
        rec.calls.append({"argv": ["os.startfile", str(path)], "cwd": None, "shell": None, "env_keys": None, "returncode": 0})

    def fake_kill(pid, sig):
        rec.calls.append({"argv": ["os.kill", pid, sig], "cwd": None, "shell": None, "env_keys": None, "returncode": 0})

    def fake_getaddrinfo(host, port, *args, **kwargs):
        # Resolver loopback hosts a loopback IPs reales (para SSRF guard).
        if host in ("localhost", "127.0.0.1", "::1"):
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", port or 0))]
        # Hosts privados típicos
        if host == "169.254.169.254":
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", port or 0))]
        if host.endswith(".internal"):
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", port or 0))]
        # Hosts públicos: IP no privada.
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", port or 0))]

    patches = [
        patch.object(subprocess, "run", rec.run),
        patch.object(subprocess, "Popen", rec.popen),
        patch("os.startfile", create=True, new=fake_startfile),
        patch("os.kill", new=fake_kill),
        patch("urllib.request.urlopen", new=url_rec.open),
        patch("socket.getaddrinfo", new=fake_getaddrinfo),
    ]

    started = []
    try:
        for p in patches:
            p.start()
            started.append(p)
        memory = MemoryStore(workspace / "memory.json")
        state = AgentState(workspace / "state.json")
        captures = workspace / "captures"
        captures.mkdir(parents=True, exist_ok=True)
        registry = ToolRegistry(memory=memory, captures_dir=captures, state=state, safety_enabled=safety_enabled)
        ctx = SmokeContext(workspace=workspace, registry=registry, state=state, subprocess_rec=rec, urllib_rec=url_rec)
        yield ctx
    finally:
        for p in started:
            try:
                p.stop()
            except Exception:
                pass
        try:
            shutil.rmtree(workspace, ignore_errors=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Helpers para los runners
# ---------------------------------------------------------------------------


def classify_result(result: dict[str, Any]) -> str:
    """Categoriza un resultado en una etiqueta breve."""
    if not isinstance(result, dict):
        return "NON_DICT"
    status = str(result.get("status") or "").lower()
    if status == "needs_confirmation":
        return "needs_confirmation"
    if status == "blocked_needs_confirmation":
        return "blocked_routine"
    if status == "needs_user":
        return "needs_user"
    if status == "needs_dependency":
        return "needs_dependency"
    if status == "failed":
        return "failed"
    if result.get("ok") is True:
        return "ok"
    if result.get("ok") is False:
        return "error"
    return "unknown"
