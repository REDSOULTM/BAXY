"""Read existing private physical captures only; no playback or new capture."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import sys
import wave

import numpy as np
from scipy.signal import correlate, correlation_lags, resample_poly
import sherpa_onnx

sys.stdout.reconfigure(encoding="utf-8")
root = Path(__file__).resolve().parents[1]
out = root / "artifacts/comprobaciones/C03/astra-analysis135"
out.mkdir(exist_ok=False)
(out / "PREREG.json").write_text(json.dumps({
    "purpose": "Offline content and alignment comparison of physical candidate134 capture",
    "sources": [134], "newPlayback": False, "sourceMutation": False,
    "method": "Registered Parakeet CPU, raw and peak-normalized; no text hints. Windows from speaking events +/-0.5s; capture start is approximate, not ADC timestamps.",
}, indent=2), encoding="utf-8")
manifest = json.loads((Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json").read_text(encoding="utf-8"))
stt = Path(manifest["stt_dir"])
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(stt / "encoder.int8.onnx"), decoder=str(stt / "decoder.int8.onnx"),
    joiner=str(stt / "joiner.int8.onnx"), tokens=str(stt / "tokens.txt"), num_threads=6,
    model_type="nemo_transducer", decoding_method="modified_beam_search", max_active_paths=8)

def transcribe(audio):
    stream = recognizer.create_stream()
    stream.accept_waveform(16000, audio.astype(np.float32))
    recognizer.decode_stream(stream)
    return str(stream.result.text or "").strip()

indexes = []
for number in [134]:
    source = root / f"artifacts/comprobaciones/C03/astra-voice{number}"
    private = Path(os.environ["LOCALAPPDATA"]) / f"BAXY/C03-voice{number}-private"
    result = json.loads((source / "AUDIO_RESULT.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (source / "EVENTS.jsonl").read_text(encoding="utf-8").splitlines()]
    signals = {}
    for kind in ["microphone", "loopback"]:
        path = private / f"{kind}.wav"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == result["streams"][kind]["sha256"]
        with wave.open(str(path), "rb") as wav:
            rate = wav.getframerate()
            samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768
            samples = samples.reshape(-1, wav.getnchannels()).mean(axis=1)
        signals[kind] = resample_poly(samples, 16000, rate) if rate != 16000 else samples
    rows = []
    for phase in ["direct"]:
        states = [e for e in events if e["phase"] == phase and e["event"] == "state"]
        start = next(e for e in states if e.get("speaking"))
        end = next(e for e in states if not e.get("speaking") and e["monotonic"] > start["monotonic"])
        start_time = dt.datetime.fromisoformat(start["utc"]).timestamp() - 0.5
        end_time = dt.datetime.fromisoformat(end["utc"]).timestamp() + 0.5
        row = {"phase": phase, "startUtc": start["utc"], "endUtc": end["utc"], "tracks": {}}
        windows = {}
        for kind, signal in signals.items():
            origin = dt.datetime.fromisoformat(result["streams"][kind]["streamReadyUtc"]).timestamp()
            first = max(0, round((start_time - origin) * 16000))
            last = min(signal.size, round((end_time - origin) * 16000))
            segment = signal[first:last]
            peak = float(np.max(np.abs(segment)))
            windows[kind] = segment
            row["tracks"][kind] = {
                "firstSample": first, "lastSample": last, "peak": peak,
                "rms": float(np.sqrt(np.mean(segment ** 2))),
                "rawTranscript": transcribe(segment),
                "normalizedTranscript": transcribe(segment * (0.8 / peak)) if peak else "",
            }
        mic, loop = windows["microphone"], windows["loopback"]
        corr = correlate(mic, loop, mode="full", method="fft")
        lags = correlation_lags(mic.size, loop.size, mode="full")
        mask = np.abs(lags) <= 16000
        best = np.flatnonzero(mask)[np.argmax(np.abs(corr[mask]))]
        row["alignment"] = {
            "correlation": float(abs(corr[best]) / (np.linalg.norm(mic) * np.linalg.norm(loop) + 1e-20)),
            "lagSeconds": float(lags[best] / 16000),
            "limit": "Whole-window correlation of separate observers, not the runtime reference or proof of no near speech",
        }
        rows.append(row)
        print(json.dumps({"source": number, **row}, ensure_ascii=False), flush=True)
    target = private / "analysis135.json"
    with target.open("x", encoding="utf-8") as stream:
        json.dump({"source": number, "rows": rows, "sttDirectory": str(stt)}, stream, indent=2, ensure_ascii=False)
    indexes.append({"source": number, "privatePath": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
(out / "RESULT_INDEX.json").write_text(json.dumps(indexes, indent=2), encoding="utf-8")
