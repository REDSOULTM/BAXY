"""Sampler de reposo aparte del producto: RSS del camino de presencia y GPU/VRAM."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def repo_baxy_processes() -> list[dict[str, object]]:
    prefix = str(REPO).rstrip("\\") + "\\"
    command = (
        "$prefix = '" + prefix.replace("'", "''") + "';"
        "Get-Process Baxy -ErrorAction SilentlyContinue |"
        "ForEach-Object {"
        "  try {"
        "    $p = [IO.Path]::GetFullPath($_.Path);"
        "    if ($p.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {"
        "      [pscustomobject]@{"
        "        Id = $_.Id; Path = $p;"
        "        WorkingSet = $_.WorkingSet64;"
        "        PrivateMemory = $_.PrivateMemorySize64"
        "      }"
        "    }"
        "  } catch {}"
        "} | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    raw = (completed.stdout or "").strip()
    if not raw:
        return []
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        return [parsed]
    return list(parsed)


def nvidia_memory() -> dict[str, object]:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    line = (completed.stdout or "").strip().splitlines()
    if not line:
        return {"nvidia_smi_memory_mib": None, "error": completed.stderr.strip() or "nvidia-smi missing"}
    used, total = [part.strip() for part in line[0].split(",", 1)]
    return {"nvidia_smi_memory_mib": f"{used}, {total}"}


def llama_server_running() -> bool:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "if (Get-Process llama-server -ErrorAction SilentlyContinue) { '1' } else { '0' }",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return (completed.stdout or "").strip() == "1"


def windows_boot_time() -> str | None:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    booted_at = (completed.stdout or "").strip()
    return booted_at or None


def sample(*, booted_at: str | None = None) -> dict[str, object]:
    processes = repo_baxy_processes()
    rss_bytes = sum(int(item.get("WorkingSet") or 0) for item in processes)
    return {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "baxy_processes": processes,
        "rss_mb": round(rss_bytes / (1024 * 1024), 1),
        "gpu": {
            "llama_server_running": llama_server_running(),
            **nvidia_memory(),
        },
        "always_on_listen": True,
        "pid": os.getpid(),
        "windows_booted_at": booted_at,
    }


def load_existing_state(output: Path) -> dict[str, object] | None:
    if not output.exists():
        return None
    state = json.loads(output.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or not isinstance(state.get("initial"), dict):
        raise ValueError(f"invalid existing sampler state: {output}")
    return state


def parse_utc(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix(".jsonl")

    existing = load_existing_state(output)
    first = existing["initial"] if existing is not None else None
    peak = float(existing.get("peak_rss_mb", 0.0)) if existing is not None else 0.0
    minimum = float(existing.get("min_rss_mb", float("inf"))) if existing is not None else float("inf")
    samples = int(existing.get("samples", 0)) if existing is not None else 0
    started_at = existing.get("started_at") if existing is not None else None
    sampler_sessions = list(existing.get("sampler_sessions", [])) if existing is not None else []
    if existing is not None and not sampler_sessions:
        sampler_sessions.append(
            {
                "started_at": first["measured_at"],
                "pid": first.get("pid"),
                "windows_booted_at": first.get("windows_booted_at"),
                "migrated_from_legacy_state": True,
            }
        )
    booted_at = windows_boot_time()
    sampler_sessions.append(
        {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "windows_booted_at": booted_at,
        }
    )
    while True:
        current = sample(booted_at=booted_at)
        rss = float(current["rss_mb"])
        peak = max(peak, rss)
        minimum = min(minimum, rss)
        samples += 1
        if first is None:
            first = current
        if started_at is None:
            started_at = first["measured_at"]
        elapsed = max(0.0, (parse_utc(current["measured_at"]) - parse_utc(started_at)).total_seconds())
        payload = {
            "started_at": started_at,
            "measured_at": current["measured_at"],
            "elapsed_s": round(elapsed, 1),
            "samples": samples,
            "rss_mb": rss,
            "peak_rss_mb": round(peak, 1),
            "min_rss_mb": round(minimum, 1),
            "initial": first,
            "latest": current,
            "gpu": current["gpu"],
            "sampler_sessions": sampler_sessions,
        }
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        with log_path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(current) + "\n")
        if args.once:
            return 0
        time.sleep(max(5.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
