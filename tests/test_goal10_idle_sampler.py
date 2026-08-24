from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts import goal10_idle_sampler as sampler


def test_sampler_resumes_existing_soak_across_process_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "soak.json"
    initial = {
        "measured_at": "2026-08-24T23:45:00+00:00",
        "rss_mb": 100.0,
        "pid": 111,
    }
    output.write_text(
        json.dumps(
            {
                "started_at": initial["measured_at"],
                "measured_at": "2026-08-25T00:00:00+00:00",
                "elapsed_s": 900.0,
                "samples": 7,
                "peak_rss_mb": 130.0,
                "min_rss_mb": 95.0,
                "initial": initial,
            }
        ),
        encoding="utf-8",
    )
    current = {
        "measured_at": "2026-08-25T00:05:00+00:00",
        "rss_mb": 90.0,
        "gpu": {"llama_server_running": True},
        "pid": 222,
    }
    monkeypatch.setattr(sampler, "windows_boot_time", lambda: "2026-08-25T00:01:00+00:00")
    monkeypatch.setattr(sampler, "sample", lambda **_kwargs: current)
    monkeypatch.setattr(sys, "argv", ["goal10_idle_sampler.py", "--output", str(output), "--once"])

    assert sampler.main() == 0

    resumed = json.loads(output.read_text(encoding="utf-8"))
    assert resumed["started_at"] == initial["measured_at"]
    assert resumed["elapsed_s"] == 1200.0
    assert resumed["samples"] == 8
    assert resumed["peak_rss_mb"] == 130.0
    assert resumed["min_rss_mb"] == 90.0
    assert resumed["initial"] == initial
    assert len(resumed["sampler_sessions"]) == 2
    assert resumed["sampler_sessions"][0]["migrated_from_legacy_state"] is True
    assert resumed["sampler_sessions"][1]["windows_booted_at"] == "2026-08-25T00:01:00+00:00"
