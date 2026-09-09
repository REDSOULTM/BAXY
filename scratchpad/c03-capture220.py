"""Verify production RAW capture on the actual WASAPI client and ADC clock."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
import threading

import numpy as np
import psutil
import sounddevice as sd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind.voice_capture import WasapiCaptureStream

OUT = ROOT / "artifacts/comprobaciones/C03/astra-capture220"
OUT.mkdir(exist_ok=False)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

helper = ROOT / "scratchpad/c03-raw-capture211.py"
spec = importlib.util.spec_from_file_location("capture211", helper)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
assert not any(p.info["name"] in {"Baxy.exe", "llama-server.exe", "piper.exe"}
               for p in psutil.process_iter(["name"]))
save("PREREG.json", {
    "utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": sha(Path(__file__)),
    "sourceSha256": sha(ROOT / "src/baxy_mind/voice_capture.py"),
    "probeSha256": sha(helper), "sounddevice": importlib.metadata.version("sounddevice"),
    "portaudioSha256": sha(Path(sd._libname)),
    "method": "Real unchanged WasapiCaptureStream, 250 consecutive frames at16k. Inspect actual borrowed IAudioClient effects through211 read-only helper after opening. Do not alter volume, synthesize speech or retain microphone PCM.",
    "criterion": "No active adaptive AEC/NS effects; 250 finite mono512 frames, no overflow, native ADC positive and strictly increasing. Record actual timing deviations. This is capture integration only, not voice or echo acceptance.",
})
rows = []
try:
    with WasapiCaptureStream(threading.Event()) as capture:
        effects = probe.stream_effects(capture._stream)
        save("ACTUAL_STREAM_EFFECTS.json", effects)
        forbidden = {"6f64adbe-8211-11e2-8c70-2c27d7f001fa", "6f64adbf-8211-11e2-8c70-2c27d7f001fa"}
        assert not any(e["id"] in forbidden and e["state"] == 1 for e in effects)
        for _ in range(250):
            audio, overflow = capture.read(512)
            assert not overflow and audio.shape == (512, 1) and np.isfinite(audio).all()
            rows.append(float(capture.adc_time))
    deltas = np.diff(rows)
    assert len(rows) == 250 and min(rows) > 0 and np.all(deltas > 0)
    result = {"frames": len(rows), "audioSeconds": len(rows) * 512 / 16000,
        "adcFirst": rows[0], "adcLast": rows[-1], "adcDeltaMin": float(deltas.min()),
        "adcDeltaMax": float(deltas.max()), "adcSpanSeconds": rows[-1] - rows[0],
        "effects": effects, "pcmRetained": False, "exitCode": 0}
    save("COMPLETE.json", result)
    print(json.dumps(result), flush=True)
except BaseException as error:
    save("FAILURE.json", {"error": repr(error), "frames": len(rows)})
    raise
