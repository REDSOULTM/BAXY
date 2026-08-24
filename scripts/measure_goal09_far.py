"""FAR of the shipped acoustic wake on recorded media. Threshold is already locked."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from scripts.measure_goal09_voice import (  # noqa: E402
    THRESHOLD,
    install_wake_assets,
    list_media,
    score_far_media,
)

SCRATCH = Path(
    os.environ.get(
        "BAXY_GOAL09_SCRATCH",
        r"C:\Users\usuario\AppData\Local\Temp\grok-goal-4eda3fa08868\implementer",
    )
)


def main() -> int:
    hours = float(os.environ.get("BAXY_GOAL09_FAR_HOURS", "30"))
    scratch = Path(os.environ.get("BAXY_GOAL09_SCRATCH", str(SCRATCH)))
    scratch.mkdir(parents=True, exist_ok=True)
    wake_dir = Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime" / "assets" / "wake"
    os.environ["BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED"] = "1"
    manifest = install_wake_assets(wake_dir)
    media = list_media()
    out = scratch / "wake_far.json"
    far = score_far_media(manifest, media, hours, checkpoint=out)
    payload = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "threshold": THRESHOLD,
        "threshold_locked_before_open": True,
        "partial": False,
        "far": far,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2)[:4000])
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
