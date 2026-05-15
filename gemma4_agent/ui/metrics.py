"""System metrics collected in a background daemon thread.

CPU / MEM are always available via psutil. GPU and TMP try multiple backends
(nvidia-smi, rocm-smi, intel_gpu_top, sensors_temperatures, powershell WMI).
Returns -1.0 when the metric is unavailable; the UI renders "N/A".
"""
from __future__ import annotations

import platform
import subprocess
import threading
import time
from typing import Any

import psutil


_OS = platform.system()


class SysMetrics:
    """Background sampler updating cpu/mem/net/gpu/tmp at ~0.7Hz."""

    def __init__(self, interval: float = 1.5) -> None:
        self.cpu: float = 0.0
        self.mem: float = 0.0
        self.net: float = 0.0
        self.gpu: float = -1.0
        self.tmp: float = -1.0
        self.disk: float = 0.0
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        self._stop_event = threading.Event()
        self._interval = interval
        self._thread = threading.Thread(target=self._loop, daemon=True, name="gemma4-sysmetrics")
        self._thread.start()

    def stop(self, *, join_timeout: float = 2.0) -> None:
        self._stop_event.set()
        self._running = False
        if self._thread.is_alive():
            self._thread.join(timeout=join_timeout)

    def _loop(self) -> None:
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            if self._stop_event.wait(self._interval):
                break

    def _update(self) -> None:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        try:
            disk = psutil.disk_usage("/").percent if _OS != "Windows" else psutil.disk_usage("C:/").percent
        except Exception:
            disk = 0.0

        nc = psutil.net_io_counters()
        now = time.time()
        dt = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net = nc
        self._last_net_t = now

        gpu = self._get_gpu()
        tmp = self._get_temp()

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp
            self.disk = disk

    def _get_gpu(self) -> float:
        # NVIDIA — fastest path
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2,
            )
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals:
                    return sum(vals) / len(vals)
        except Exception:
            pass

        if _OS == "Linux":
            try:
                r = subprocess.run(
                    ["rocm-smi", "--showuse", "--csv"],
                    capture_output=True, text=True, timeout=2,
                )
                if r.returncode == 0:
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split(",")
                        if len(parts) >= 2:
                            try:
                                return float(parts[1].strip().replace("%", ""))
                            except ValueError:
                                pass
            except Exception:
                pass

        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}  # type: ignore[attr-defined]
            candidates = ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                          "cpu-thermal", "zenpower", "it8688"]
            for name in candidates:
                if name in temps and temps[name]:
                    return temps[name][0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass

        if _OS == "Windows":
            try:
                r = subprocess.run(
                    ["powershell", "-Command",
                     "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"],
                    capture_output=True, text=True, timeout=3,
                )
                if r.returncode == 0 and r.stdout.strip():
                    raw = float(r.stdout.strip().split("\n")[0])
                    return (raw / 10.0) - 273.15
            except Exception:
                pass

        return -1.0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "cpu":  self.cpu,
                "mem":  self.mem,
                "net":  self.net,
                "gpu":  self.gpu,
                "tmp":  self.tmp,
                "disk": self.disk,
            }


def boot_uptime_str() -> str:
    try:
        elapsed = time.time() - psutil.boot_time()
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        return f"{h:02d}:{m:02d}"
    except Exception:
        return "--:--"


def proc_count() -> int:
    try:
        return len(psutil.pids())
    except Exception:
        return -1


def os_short() -> str:
    return {"Windows": "WIN", "Darwin": "macOS", "Linux": "LINUX"}.get(_OS, _OS.upper())
