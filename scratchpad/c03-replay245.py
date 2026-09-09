"""Replay exact243 clean PCM through product segmentation and installed ASR."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import queue
import sys
import threading

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import baxy_mind.voice as voice

OUT = ROOT / "artifacts/comprobaciones/C03/astra-replay245"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-replay245-private"
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

prior = json.loads((ROOT / "artifacts/comprobaciones/C03/astra-voice243/RESULTS.json").read_text(encoding="utf-8"))
source = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-voice243-private/tap243.npz"
assert sha(source) == next(row["sha256"] for row in prior["privateFiles"] if Path(row["path"]) == source)
data = np.load(source)
audio, near, reference, observed = [data[key] for key in ["clean", "microphone", "reference", "observations"]]
assert importlib.metadata.version("sherpa-onnx") == "1.13.4+baxy.2"
save(OUT / "PREREG.json", {
    "method": "All1317 exact243 cleaned frames through real product capture segmentation and fresh SileroVad. Recorded speaking state; echo guard receives the recorded delayed raw microphone/reference pair, as returned by DTLN512244. Inert device/output/ducker only, no physical effects. Decode actual queued segments with installed baxy.2. Compare actual VAD and guard to243; keep mismatches honest.",
    "hypothesis": "Reproduce the physical243 interruption and actual queued segments on integrated source242, before changing any acoustic algorithm. Compare VAD, actual guard and speaking timeline against243; no threshold or decoder change.",
    "sourceSha256": sha(ROOT / "src/baxy_mind/voice.py"), "scriptSha256": sha(Path(__file__)),
    "inputSha256": sha(source), "thresholdsChanged": False,
})
event = threading.Event()

class FiniteStream:
    device = None
    reads = 0
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass
    def read(self, samples):
        assert samples == 512
        if self.reads == len(audio):
            event.set()
            return np.zeros((512, 1), np.float32), False
        frame = audio[self.reads]
        self.reads += 1
        return frame[:, None], False

stream = FiniteStream()

class Output:
    available = False
    @property
    def speaking(self):
        return bool(observed[max(0, stream.reads - 1), 3])
    def start(self):
        pass

class Ducker:
    def duck(self):
        return True
    def restore(self):
        return True

voice.create_speech_output = lambda _: Output()
voice._PcmCaptureStream = lambda *_: stream
pair_record = json.loads((ROOT / "artifacts/comprobaciones/C03/astra-echo244/RESULTS.json").read_text(encoding="utf-8"))
pair_path = Path(pair_record["privatePath"])
assert sha(pair_path) == pair_record["privateSha256"]
pairs = np.load(pair_path)
original_guard = voice._looks_like_echo
guards = []

def recorded_guard(_microphone, _reference):
    i = stream.reads - 1
    result = original_guard(pairs["microphone"][i], pairs["reference"][i])
    guards.append({"frame": i, "result": result, "recorded": observed[i, 5]})
    return result

voice._looks_like_echo = recorded_guard
requests, events, transcripts, cancellations = [], [], [], []
engine = voice.VoiceEngine(transcripts.append, events.append)
engine.load()
engine._mode = "direct"
engine._pcm_inbox = queue.Queue()
engine._ducker = Ducker()
engine.probe = lambda: {}
engine.cancel_speech = lambda: cancellations.append(stream.reads - 1)
probabilities = []
original_vad = engine._vad.process

def observe_vad(frame):
    result = original_vad(frame)
    probabilities.append(result)
    return result

engine._vad.process = observe_vad

class Sink:
    def put_nowait(self, request):
        requests.append((stream.reads, request))

engine._capture_loop(stop_event=event, decode_queue=Sink(), capture_ready_event=threading.Event())
assert not any(e.get("event") == "error" for e in events), events
assert stream.reads == len(audio) == len(probabilities)
segments, signals = [], {}
for index, (end, request) in enumerate(requests):
    first = end * 512 - len(request.audio)
    assert np.array_equal(request.audio, audio.ravel()[first:end * 512])
    signals[f"segment{index}"] = request.audio
    segments.append({"index": index, "firstFrame": first // 512, "endFrameExclusive": end,
        "seconds": len(request.audio) / 16000, "text": engine.transcribe_pcm(request.audio)})
np.savez(PRIVATE / "segments245.npz", **signals)
energy = np.sqrt(np.mean(audio ** 2, axis=1))
floor = .002
rows = []
guard_by_frame = {row["frame"]: row["result"] for row in guards}
for i, probability in enumerate(probabilities):
    if probability < .5:
        floor = .98 * floor + .02 * energy[i]
    threshold = max(.004, floor * 1.8)
    if probability >= .5:
        rows.append({"frame": i, "time": observed[i, 0], "probability": probability,
            "energy": float(energy[i]), "speaking": bool(observed[i, 3]),
            "echo": guard_by_frame.get(i), "bargeEnergyThreshold": float(threshold),
            "belowBargeEnergy": bool(energy[i] < threshold)})
save(OUT / "SPEECH_FRAMES.json", rows)
save(PRIVATE / "SEGMENTS.json", segments)
result = {"frames": len(audio), "segments": segments, "cancelFrames": cancellations,
    "vadMaximumDifference": float(np.max(np.abs(np.asarray(probabilities) - observed[:, 4]))),
    "guardComparisons": len(guards), "guardDifferences": [r for r in guards if r["result"] != r["recorded"]],
    "speechFrames": len(rows), "unrejectedBelowBargeEnergyWhileSpeaking": sum(
        r["speaking"] and r["echo"] is False and r["belowBargeEnergy"] for r in rows),
    "privateFiles": [{"path": str(p), "sha256": sha(p)} for p in PRIVATE.iterdir()], "exitCode": 0}
save(OUT / "RESULTS.json", result)
print(json.dumps(result), flush=True)
