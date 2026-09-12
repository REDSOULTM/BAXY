"""Mide la memoria GPU dedicada por proceso de las apps que abrirá la tanda de apps.

Por qué existe: el muestreador heredado (`ProcessTreeGpuSampler`) atribuye la GPU por PID al
árbol del proceso lanzado, y `WindowsInstalledApplicationOpenProvider` arranca la app con
`UseShellExecute = false`, así que la app queda como hija de `baxy-core.exe` y su GPU cuenta
contra la guarda de 3800 MiB. Con el modelo en 3494 MiB medidos en SYSTEM1028 el margen es de
~300 MiB, y una app Chromium puede gastarlo. Este script mide el gasto real en esta máquina
ANTES de sellar el panel, en vez de suponerlo.

Uso:
    python scratchpad/c03-app-gpu-cost.py <nombre-proceso> [...]

Lee el mismo contador de Windows que la guarda: "GPU Process Memory" / "Dedicated Usage".
No lanza nada, no cierra nada: sólo mide lo que ya está en ejecución.
"""
from __future__ import annotations

import re
import sys
import time

import psutil
import win32pdh

PID = re.compile(r"^pid_([0-9]+)_", re.IGNORECASE)


def sample() -> dict[int, int]:
    query = win32pdh.OpenQuery()
    try:
        path = win32pdh.MakeCounterPath(
            (None, "GPU Process Memory", "*", None, 0, "Dedicated Usage"))
        counter = win32pdh.AddCounter(query, path)
        win32pdh.CollectQueryData(query)
        time.sleep(1.0)
        win32pdh.CollectQueryData(query)
        rows = win32pdh.GetFormattedCounterArray(counter, win32pdh.PDH_FMT_LARGE)
    finally:
        win32pdh.CloseQuery(query)
    totals: dict[int, int] = {}
    for instance, value in rows.items():
        match = PID.match(instance)
        if match is not None:
            pid = int(match.group(1))
            totals[pid] = totals.get(pid, 0) + max(0, int(value))
    return totals


def main(argv: list[str]) -> int:
    wanted = {name.lower() for name in argv[1:]}
    if not wanted:
        print(__doc__)
        return 2
    totals = sample()
    grouped: dict[str, dict[str, float]] = {}
    for process in psutil.process_iter(["pid", "name", "memory_info"]):
        name = (process.info["name"] or "").lower()
        root = next((w for w in wanted if w in name), None)
        if root is None:
            continue
        entry = grouped.setdefault(root, {"processes": 0, "gpu_mib": 0.0, "rss_mib": 0.0})
        entry["processes"] += 1
        entry["gpu_mib"] += totals.get(process.info["pid"], 0) / 2 ** 20
        entry["rss_mib"] += (process.info["memory_info"].rss if process.info["memory_info"] else 0) / 2 ** 20
    for name in sorted(wanted):
        entry = grouped.get(name)
        if entry is None:
            print(f"{name:24} no en ejecución")
            continue
        print(f"{name:24} procesos {entry['processes']:3}  GPU dedicada {entry['gpu_mib']:9.2f} MiB"
              f"  RSS {entry['rss_mib']:9.2f} MiB")
    print(f"\nGPU dedicada total de lo pedido: "
          f"{sum(e['gpu_mib'] for e in grouped.values()):.2f} MiB")
    print(f"RAM libre: {psutil.virtual_memory().available / 2 ** 20:.0f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
