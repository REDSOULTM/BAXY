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


def sample() -> dict[str, object]:
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
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix(".jsonl")

    first: dict[str, object] | None = None
    peak = 0.0
    samples = 0
    started = time.time()
    while True:
        current = sample()
        rss = float(current["rss_mb"])
        peak = max(peak, rss)
        samples += 1
        if first is None:
            first = current
        payload = {
            "started_at": first["measured_at"],
            "measured_at": current["measured_at"],
            "elapsed_s": round(time.time() - started, 1),
            "samples": samples,
            "rss_mb": rss,
            "peak_rss_mb": round(peak, 1),
            "min_rss_mb": min(float(first["rss_mb"]), rss),
            "initial": first,
            "latest": current,
            "gpu": current["gpu"],
        }
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        with log_path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(current) + "\n")
        if args.once:
            return 0
        time.sleep(max(5.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
