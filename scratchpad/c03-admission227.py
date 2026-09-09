"""Observe exact production admission locals on the four fixed RAW human controls."""
import hashlib
import json
import os
from pathlib import Path
import queue
import sys
import threading

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import baxy_mind.voice as voice

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-admission227"
OUT.mkdir(exist_ok=False)
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY"

def read(p):
    return json.loads(p.read_text(encoding="utf-8"))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

assert sha(ROOT / "src/baxy_mind/voice.py") == read(BASE / "astra-source225-snapshot/FILES.json")["src/baxy_mind/voice.py"]
capture = read(BASE / "astra-raw-capture211/RESULTS.json")
raw_path = PRIVATE / "C03-raw-capture211-private/raw.npz"
assert sha(raw_path) == next(r["sha256"] for r in capture["streams"] if r["mode"] == "raw")
raw = np.load(raw_path)
mic, ref, timing = [raw[k] for k in ["microphone", "reference", "timing"]]
origin = capture["playback"]["streamTime"] + capture["playback"]["latency"]
intervals = np.asarray(read(BASE / "astra-raw-capture211/PREREG.json")["intervalsSeconds"]) + origin
mask_time = timing[:, 0] - .032
speaking = np.any((mask_time[:, None] >= intervals[None, :, 0]) & (mask_time[:, None] < intervals[None, :, 1]), axis=1)
humans = read(BASE / "astra-human195/DOWNLOADS.json")
inputs = [r for r in read(BASE / "astra-raw-human213/RESULTS.json") if r["condition"] == "raw_speex"]
save(OUT / "PREREG.json", {
    "method": "Same four RAW+human213 full cleaned signals and fixed speaking mask226, actual source225 capture loop/Silero/guard. Inert ducker observes only scalar locals from its caller capture loop at actual begin_utterance. No ASR/model needed: queued PCM must match226 hashes/ranges exactly. No thresholds/source changed.",
    "hypothesis": "The pre-human echo segment opens with fewer than the three consecutive eligible frames already required for interruption.",
    "scriptSha256": sha(Path(__file__)), "sourceSha256": sha(ROOT / "src/baxy_mind/voice.py"),
    "inputs": [{k: r[k] for k in ["human", "condition", "onset", "gain", "sha256"]} for r in inputs],
    "limitation": "Offline diagnostic with fixed approximate playback mask, not physical counterfactual cancellation or final human acceptance.",
})
original_guard = voice._looks_like_echo
vad = voice.SileroVad()
results = []
for row in inputs:
    source = PRIVATE / "C03-raw-human213-private" / f'h{row["human"]}-raw_speex.npz'
    assert sha(source) == row["sha256"]
    audio = np.load(source)["clean"]
    human = humans[row["human"]]
    assert sha(Path(human["asset"])) == human["sha256"]
    rate, original = wavfile.read(human["asset"])
    assert rate == 16000
    near = np.zeros(mic.size, np.float32)
    near[row["onset"]:row["onset"] + len(original)] = original * row["gain"]
    incoming = near.reshape(mic.shape) + mic
    stop = threading.Event()
    admissions, requests, events, cancellations = [], [], [], []
    class Stream:
        reads = 0
        device = None
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def read(self, samples):
            assert samples == 512
            if self.reads == len(audio):
                stop.set()
                return np.zeros((512, 1), np.float32), False
            value = audio[self.reads]
            self.reads += 1
            return value[:, None], False
    stream = Stream()
    class Output:
        available = False
        @property
        def speaking(self):
            return bool(speaking[max(0, stream.reads - 1)])
    class Ducker:
        def duck(self):
            caller = sys._getframe(2)
            assert caller.f_code.co_name == "_capture_loop"
            scalars = {key: caller.f_locals[key] for key in ["barge_frames", "noise_floor", "speech", "energy", "probability"]}
            admissions.append({"frame": stream.reads - 1, "speaking": bool(speaking[stream.reads - 1]), **scalars})
            return True
        def restore(self):
            return True
    class Sink:
        def put_nowait(self, request):
            requests.append((stream.reads, request))
    voice.create_speech_output = lambda _: Output()
    voice._PcmCaptureStream = lambda *_: stream
    def paired_guard(_mic, _ref):
        i = stream.reads - 1
        return original_guard(incoming[i - 1] * 32768 if i else np.zeros(512), ref[i - 1] if i else np.zeros(4512))
    voice._looks_like_echo = paired_guard
    engine = voice.VoiceEngine(lambda _: None, events.append)
    engine._mode = "direct"
    engine._pcm_inbox = queue.Queue()
    engine._ducker = Ducker()
    engine.probe = lambda: {}
    engine._vad = vad
    vad.reset()
    engine.cancel_speech = lambda: cancellations.append(stream.reads - 1)
    engine._capture_loop(stop_event=stop, decode_queue=Sink(), capture_ready_event=threading.Event())
    assert not any(e.get("event") == "error" for e in events), events
    segments = [{"firstSample": end * 512 - len(request.audio), "lastSample": end * 512,
        "pcmSha256": hashlib.sha256(request.audio.tobytes()).hexdigest()} for end, request in requests]
    prior = next(r for r in read(BASE / "astra-human226/RESULTS.json") if r["human"] == row["human"] and r["condition"] == "raw_speex")["variants"][1]
    assert segments == [{k: s[k] for k in ["firstSample", "lastSample", "pcmSha256"]} for s in prior["segments"]]
    assert cancellations == prior["cancellations"]
    result = {"human": row["human"], "admissions": admissions, "segments": segments,
        "cancellations": cancellations, "matches226": True, "humanInsertionSample": row["onset"]}
    results.append(result)
    save(OUT / "RESULTS.json", results)
    print(json.dumps({"human": row["human"], "admissions": admissions}), flush=True)
save(OUT / "COMPLETE.json", {"controls": 4, "pcmParity226": 4, "exitCode": 0})
