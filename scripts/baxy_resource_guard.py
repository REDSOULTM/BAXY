"""Fail-safe resource monitor for controlled BAXY desktop runs.

Start this process before BAXY.  It samples the exact BAXY process family and
terminates that family if sustained CPU/GPU pressure or memory growth could
make Windows unresponsive.  It never terminates unrelated processes.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import threading
import time
from typing import Any

import psutil


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    total_cpu_percent: float = 85.0
    baxy_cpu_percent: float = 70.0
    system_ram_percent: float = 90.0
    baxy_rss_mib: float = 6144.0
    gpu_percent: float = 90.0
    gpu_memory_percent: float = 85.0
    consecutive_samples: int = 3
    gpu_consecutive_samples: int = 5


class BreachTracker:
    def __init__(self, limits: ResourceLimits) -> None:
        self._limits = limits
        self._counts: defaultdict[str, int] = defaultdict(int)

    def observe(self, sample: dict[str, Any]) -> list[str]:
        gpu = sample.get("gpu") or {}
        checks = {
            "total_cpu": float(sample["total_cpu_percent"])
            >= self._limits.total_cpu_percent,
            "baxy_cpu": float(sample["baxy_cpu_percent"])
            >= self._limits.baxy_cpu_percent,
            "system_ram": float(sample["system_ram_percent"])
            >= self._limits.system_ram_percent
            and float(sample["baxy_rss_mib"]) >= 1024.0,
            "baxy_rss": float(sample["baxy_rss_mib"]) >= self._limits.baxy_rss_mib,
            "gpu": bool(sample["processes"])
            and gpu.get("utilization_percent") is not None
            and float(gpu["utilization_percent"]) >= self._limits.gpu_percent,
            "gpu_memory": bool(sample["processes"])
            and gpu.get("memory_percent") is not None
            and float(gpu["memory_percent"]) >= self._limits.gpu_memory_percent,
        }
        tripped: list[str] = []
        for name, active in checks.items():
            self._counts[name] = self._counts[name] + 1 if active else 0
            required = (
                self._limits.gpu_consecutive_samples
                if name == "gpu"
                else self._limits.consecutive_samples
            )
            if self._counts[name] >= required:
                tripped.append(name)
        return tripped


def _is_baxy_seed(process: psutil.Process) -> bool:
    try:
        info = getattr(process, "info", {})
        name = str(info.get("name") or process.name()).casefold()
        command_parts = None
        if name in {"python.exe", "pythonw.exe"}:
            command_parts = process.cmdline()
        command = " ".join(command_parts or ()).casefold()
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return False
    if name in {"baxy.exe", "baxy-core.exe", "llama-server.exe"}:
        return True
    return name in {"python.exe", "pythonw.exe"} and (
        "-m baxy_mind" in command or "baxy_mind.router_worker" in command
    )


def baxy_process_family() -> list[psutil.Process]:
    seeds = [
        process
        for process in psutil.process_iter(attrs=("name",))
        if _is_baxy_seed(process)
    ]
    family: dict[int, psutil.Process] = {process.pid: process for process in seeds}
    for process in seeds:
        try:
            for child in process.children(recursive=True):
                family[child.pid] = child
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return list(family.values())


def _read_gpu_sample() -> dict[str, float | None]:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=2.0,
        )
        fields = [
            field.strip() for field in completed.stdout.splitlines()[0].split(",")
        ]
        utilization, used, total = (float(field) for field in fields[:3])
        return {
            "utilization_percent": utilization,
            "memory_used_mib": used,
            "memory_total_mib": total,
            "memory_percent": round(used * 100.0 / total, 2) if total else None,
        }
    except (FileNotFoundError, IndexError, ValueError, subprocess.SubprocessError):
        return {
            "utilization_percent": None,
            "memory_used_mib": None,
            "memory_total_mib": None,
            "memory_percent": None,
        }


class GpuSampler:
    """Keep slow vendor telemetry away from the CPU safety clock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._sample = {
            "utilization_percent": None,
            "memory_used_mib": None,
            "memory_total_mib": None,
            "memory_percent": None,
        }
        self._worker = threading.Thread(
            target=self._run,
            name="baxy-resource-gpu-sampler",
            daemon=True,
        )

    def start(self) -> None:
        self._worker.start()

    def latest(self) -> dict[str, float | None]:
        with self._lock:
            return dict(self._sample)

    def close(self) -> None:
        self._stop.set()
        self._worker.join(timeout=3.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            sample = _read_gpu_sample()
            with self._lock:
                self._sample = sample
            self._stop.wait(1.0)


def _prime_cpu(processes: list[psutil.Process]) -> None:
    psutil.cpu_percent(interval=None)
    for process in processes:
        try:
            process.cpu_percent(interval=None)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue


def take_sample(
    known: dict[int, psutil.Process],
    gpu: dict[str, float | None],
) -> dict[str, Any]:
    discovered = baxy_process_family()
    for process in discovered:
        if process.pid not in known:
            try:
                process.cpu_percent(interval=None)
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            known[process.pid] = process
    active = {process.pid: process for process in discovered}
    for pid in tuple(known):
        if pid not in active:
            del known[pid]
    processes = list(known.values())

    cpu_raw = 0.0
    rss = 0
    rows: list[dict[str, Any]] = []
    for process in processes:
        try:
            process_cpu = process.cpu_percent(interval=None)
            process_rss = process.memory_info().rss
            cpu_raw += process_cpu
            rss += process_rss
            rows.append(
                {
                    "pid": process.pid,
                    "name": process.name(),
                    "cpu_percent_of_one_core": round(process_cpu, 2),
                    "rss_mib": round(process_rss / 1024 / 1024, 2),
                }
            )
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    logical = psutil.cpu_count(logical=True) or 1
    return {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "total_cpu_percent": psutil.cpu_percent(interval=None),
        "baxy_cpu_percent": round(cpu_raw / logical, 2),
        "system_ram_percent": psutil.virtual_memory().percent,
        "baxy_rss_mib": round(rss / 1024 / 1024, 2),
        "gpu": gpu,
        "processes": sorted(rows, key=lambda row: int(row["pid"])),
    }


def terminate_baxy_family(processes: list[psutil.Process]) -> list[int]:
    targets: dict[int, psutil.Process] = {}
    for process in processes:
        targets[process.pid] = process
        try:
            for child in process.children(recursive=True):
                targets[child.pid] = child
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    killed: list[int] = []
    for process in reversed(list(targets.values())):
        try:
            process.kill()
            killed.append(process.pid)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    psutil.wait_procs(list(targets.values()), timeout=3.0)
    return killed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--duration", type=float, default=300.0)
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()

    try:
        psutil.Process().nice(psutil.HIGH_PRIORITY_CLASS)
    except (AttributeError, psutil.AccessDenied, psutil.Error):
        pass

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    limits = ResourceLimits()
    tracker = BreachTracker(limits)
    known = {process.pid: process for process in baxy_process_family()}
    _prime_cpu(list(known.values()))
    gpu_sampler = GpuSampler()
    gpu_sampler.start()
    started = time.monotonic()
    peak: dict[str, float] = defaultdict(float)
    samples = 0
    action = "completed"
    reasons: list[str] = []
    killed: list[int] = []

    try:
        with output.with_suffix(".jsonl").open("w", encoding="utf-8") as log:
            while time.monotonic() - started < max(0.0, args.duration):
                time.sleep(max(0.2, args.interval))
                current = take_sample(known, gpu_sampler.latest())
                samples += 1
                for key in (
                    "total_cpu_percent",
                    "baxy_cpu_percent",
                    "system_ram_percent",
                    "baxy_rss_mib",
                ):
                    peak[key] = max(peak[key], float(current[key]))
                gpu = current["gpu"]
                for key in ("utilization_percent", "memory_percent"):
                    if gpu[key] is not None:
                        peak[f"gpu_{key}"] = max(peak[f"gpu_{key}"], float(gpu[key]))
                log.write(json.dumps(current, ensure_ascii=False) + "\n")
                log.flush()
                reasons = tracker.observe(current)
                if reasons:
                    action = "baxy_process_family_killed"
                    killed = terminate_baxy_family(baxy_process_family())
                    break
    finally:
        gpu_sampler.close()

    summary = {
        "schema": "baxy-resource-guard-v1",
        "action": action,
        "reasons": reasons,
        "killed_pids": killed,
        "samples": samples,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "limits": asdict(limits),
        "peak": dict(peak),
    }
    output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 2 if reasons else 0


if __name__ == "__main__":
    raise SystemExit(main())
