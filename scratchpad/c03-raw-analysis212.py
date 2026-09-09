"""Fixed four-way comparison on paired physical211 inputs."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind.speex_aec import EchoCanceller
from baxy_mind.voice import SileroVad, _looks_like_echo

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

base = ROOT / "artifacts/comprobaciones/C03"
assert (base / "astra-raw-capture211/COMPLETE.json").is_file()
out = base / "astra-raw-analysis212"
out.mkdir(exist_ok=False)
source = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-raw-capture211-private"
private = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-raw-analysis212-private"
private.mkdir(exist_ok=False)
captured = json.loads((base / "astra-raw-capture211/RESULTS.json").read_text(encoding="utf-8"))
assert captured["restoredExactly"] and not captured["errors"]
prereg211 = json.loads((base / "astra-raw-capture211/PREREG.json").read_text(encoding="utf-8"))
origin = captured["playback"]["streamTime"] + captured["playback"]["latency"]
intervals = np.asarray(prereg211["intervalsSeconds"]) + origin
save(out / "PREREG.json", {
    "utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": digest(Path(__file__)),
    "inputs": captured["streams"],
    "method": "Default/RAW simultaneous211 mic/reference, each unchanged or passed through current Speex. Fresh Silero per condition, unchanged .5VAD/.004energy/1.8noise/3consecutive/echo guard. No gain/filter/threshold sweeps.",
    "speakingMask": "Fixed scheduled original playback intervals from output stream time plus output latency. Speex mask delayed512samples for its known output delay. Timestamp mask approximate near boundaries; report full and masked VAD counts.",
    "limitation": "No live utterance reset or actual cancellation of playback; candidate events only. Pure physical echo, not human double-talk or final acceptance.",
    "sources": {name: digest(ROOT / f"src/baxy_mind/{name}.py") for name in ["voice", "speex_aec", "voice_aec"]},
})
results = []
vad = SileroVad()
for source_row in captured["streams"]:
    mode = source_row["mode"]
    path = source / f"{mode}.npz"
    assert digest(path) == source_row["sha256"]
    data = np.load(path)
    microphone, reference, timing = [data[k] for k in ["microphone", "reference", "timing"]]
    assert np.array_equal(reference[1:, :-512], reference[:-1, 512:])
    assert np.all(np.diff(timing[:, 2]) == 512)
    for use_speex in [False, True]:
        engine = EchoCanceller() if use_speex else None
        delay = .032 if use_speex else 0
        mask_time = timing[:, 0] - delay
        speaking = np.any((mask_time[:, None] >= intervals[None, :, 0]) &
                          (mask_time[:, None] < intervals[None, :, 1]), axis=1)
        vad.reset()
        clean = np.empty_like(microphone)
        measures = np.zeros((len(microphone), 6), np.float64)
        floor, run, fires = .002, 0, []
        try:
            for i in range(len(microphone)):
                start = time.perf_counter()
                if engine:
                    frame, paired_mic, paired_ref = engine.process(microphone[i], reference[i])
                else:
                    frame, paired_mic, paired_ref = microphone[i], microphone[i] * 32768, reference[i]
                elapsed = (time.perf_counter() - start) * 1000
                clean[i] = frame
                probability = vad.process(frame)
                energy = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))
                if probability < .5:
                    floor = .98 * floor + .02 * energy
                guard = _looks_like_echo(paired_mic, paired_ref)
                if probability >= .5 and speaking[i] and not guard and energy >= max(.004, floor * 1.8):
                    run += 1
                    if run == 3:
                        fires.append({"frame": i, "playbackSeconds": float(mask_time[i] - origin)})
                else:
                    run = 0
                measures[i] = [probability, energy, floor, guard, run, elapsed]
        finally:
            if engine:
                engine.close()
        output = private / f"{mode}-{'speex' if use_speex else 'none'}.npz"
        np.savez(output, clean=clean, measures=measures, speaking=speaking)
        rms_in = float(np.sqrt(np.mean(microphone[speaking].astype(np.float64) ** 2)))
        rms_out = float(np.sqrt(np.mean(clean[speaking].astype(np.float64) ** 2)))
        row = {"mode": mode, "speex": use_speex, "frames": len(microphone),
            "speakingFrames": int(speaking.sum()), "speechFramesAll": int((measures[:, 0] >= .5).sum()),
            "speechFramesSpeaking": int(((measures[:, 0] >= .5) & speaking).sum()),
            "guardTrueSpeaking": int(((measures[:, 3] == 1) & speaking).sum()),
            "candidateInterruptions": fires, "speakingInputRms": rms_in, "speakingOutputRms": rms_out,
            "dspP99Ms": float(np.quantile(measures[:, 5], .99)), "sha256": digest(output)}
        results.append(row)
        save(out / "RESULTS.json", results)
        print(json.dumps(row), flush=True)
save(out / "COMPLETE.json", {"conditions": 4, "exitCode": 0})
