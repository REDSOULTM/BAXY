"""CPU/RAM/GPU rápido (in-process) — extraído de tools.py (2026-06-09, ratchet
archivo-dios). La versión WMI (PowerShell + 3 queries CIM, Win32_VideoController
es el más lento) tardaba ~2.4s. psutil da CPU/RAM in-process (~ms) y nvidia-smi la
GPU (~100ms, lo que el user ve en su panel). Fallback a WMI si psutil no está.

Devuelve un dict listo para _ok(**...) o un dict con 'error' para _err(**...). El
`info` conserva las claves cpu/os/gpu para no cambiar lo que el LLM lee.
"""
from __future__ import annotations

import subprocess
from typing import Any


def gpu_info_fast() -> Any:
    """GPU vía nvidia-smi (~100ms). Si no hay NVIDIA, marcador honesto (no spawnea
    el WMI lento — el nombre de la iGPU no es lo que el user pregunta con '¿cuánta
    VRAM tengo?'). Best-effort."""
    try:
        proc = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,memory.used,utilization.gpu,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4)
        gpus = []
        for ln in (proc.stdout or "").strip().splitlines():
            parts = [p.strip() for p in ln.split(",")]
            if len(parts) >= 5:
                gpus.append({
                    "Name": parts[0], "MemoryTotalMB": parts[1],
                    "MemoryUsedMB": parts[2], "UtilizationPct": parts[3],
                    "DriverVersion": parts[4],
                })
        if gpus:
            return gpus if len(gpus) > 1 else gpus[0]
    except Exception:
        pass
    return {"Name": "no NVIDIA GPU detected (or nvidia-smi unavailable)"}


def cpu_ram_gpu() -> dict[str, Any]:
    """Devuelve {'ok': True, 'info': {...}, 'source': ...} o {'error': ...}."""
    info: dict[str, Any] = {}
    fast_ok = False
    try:
        import psutil
        _vm = psutil.virtual_memory()
        # interval=None es no-bloqueante (usa la lectura previa) e instantáneo.
        _cpu_pct = psutil.cpu_percent(interval=None)
        _cpu_name = ""
        try:
            import winreg  # type: ignore
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                _cpu_name = str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
        except Exception:
            _cpu_name = ""
        info["cpu"] = {"Name": _cpu_name, "LoadPercentage": round(_cpu_pct)}
        # WMI reporta KB; mantenemos KB para no cambiar la interpretación previa.
        info["os"] = {
            "TotalVisibleMemorySize": int(_vm.total / 1024),
            "FreePhysicalMemory": int(_vm.available / 1024),
        }
        fast_ok = True
    except Exception:
        fast_ok = False

    if fast_ok:
        info["gpu"] = gpu_info_fast()
        return {"ok": True, "info": info, "source": "psutil+nvidia-smi"}

    # FALLBACK WMI (lento pero universal).
    from .tools import parse_ps_json
    script = r"""
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name,LoadPercentage
$os = Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory
$gpu = Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion
[PSCustomObject]@{ cpu=$cpu; os=$os; gpu=$gpu } | ConvertTo-Json -Depth 4
"""
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return {"error": "system_cpu_ram_gpu timeout", "reason": "powershell_cim_timeout"}
    ok, info_wmi = parse_ps_json(proc.stdout)
    if not ok:
        return {"error": "system_cpu_ram_gpu invalid JSON", "stdout": info_wmi}
    return {"ok": True, "info": info_wmi, "source": "wmi"}


__all__ = ["cpu_ram_gpu", "gpu_info_fast"]
