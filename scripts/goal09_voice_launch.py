"""Drive the shipped voice engine the same way the App does: start/speak/cancel."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

SCRATCH = Path(
    os.environ.get(
        "BAXY_GOAL09_SCRATCH",
        r"C:\Users\usuario\AppData\Local\Temp\grok-goal-4eda3fa08868\implementer",
    )
)
os.environ.setdefault(
    "BAXY_VOICE_WAKE_MANIFEST",
    str(Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime" / "assets" / "wake" / "baxy-wakeword-v1.json"),
)
os.environ.setdefault("BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED", "1")
os.environ.setdefault(
    "BAXY_MIND_STT_DIR",
    str(Path.home() / ".gemma4" / "models" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"),
)

import numpy as np

from baxy_mind.voice import SAMPLE_RATE, VoiceEngine


def one_run(index: int) -> dict:
    events: list[dict] = []
    transcripts: list[str] = []
    engine = VoiceEngine(transcripts.append, events.append)
    engine.use_pcm_source()
    started = engine.start("wake")
    status = engine.status()
    spoke = engine.speak("Listo, te escucho.")
    deadline = time.monotonic() + 4.0
    while not engine.speaking and time.monotonic() < deadline:
        time.sleep(0.02)
    speaking = engine.speaking
    time.sleep(0.25)
    engine.cancel_speech()
    deadline = time.monotonic() + 2.0
    while engine.speaking and time.monotonic() < deadline:
        time.sleep(0.02)
    cancelled = not engine.speaking
    noise = (np.random.default_rng(index).standard_normal(SAMPLE_RATE) * 0.01).astype(
        np.float32
    )
    engine.ingest_pcm(noise)
    time.sleep(0.3)
    engine.stop()
    engine.shutdown()
    return {
        "run": index,
        "started": started,
        "mode": status.get("mode"),
        "wakeWord": status.get("wakeWord"),
        "ttsNeural": status.get("ttsNeural"),
        "ttsVoice": status.get("ttsVoice"),
        "spoke": spoke,
        "speaking_observed": speaking,
        "cancelled_mid_utterance": cancelled,
        "events": [event.get("event") for event in events[:12]],
        "last_error": engine.last_error,
    }


def main() -> int:
    runs = [one_run(1), one_run(2)]
    ok = all(
        run["started"] and run["spoke"] and run["cancelled_mid_utterance"] for run in runs
    )
    payload = {"ok": ok, "runs": runs}
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / "voice_launch.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
