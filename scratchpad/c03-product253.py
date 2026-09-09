"""Evaluate all frozen248 outputs through actual product segmentation and ASR."""
from datetime import datetime, timezone
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

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-product253"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-product253-private"

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

assert read(BASE / "astra-linear250/COMPLETE.json")["outputs"] == 11
inputs = read(BASE / "astra-linear250/RESULTS.json")
final_inputs = {r["case"]: r for r in read(BASE / "astra-webrtc248/RESULTS.json")}
assert importlib.metadata.version("sherpa-onnx") == "1.13.4+baxy.2"
assert sha(ROOT / "src/baxy_mind/voice.py") == read(BASE / "astra-source242-snapshot/FILES.json")["src/baxy_mind/voice.py"]
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)
save(OUT / "PREREG.json", {
    "utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": sha(Path(__file__)),
    "method": "One offline hypothesis: diagnostic copy capture242. Aligned linear250+64samples provides recognition and candidate-onset VAD; final248 provides independent confirmation VAD and barge energy. Speech continuity uses either VAD at existing0.5; raw echo guard256 unchanged. Buffer candidate from linear onset, publish only after final confirms (three qualified frames during TTS). TTS ending alone never authorizes a candidate. Same0.7s trailing silence, no ASR hints/decoder/weights/gain changes. All11timelines plus8fixedwindows. No effects or source edits.",
    "criterion": "Compare pre-suppressor linear250 to original final249 and DTLN512239 on identical ten timelines, plus243 failure for human content and echo. Report every literal, not merely zero interruptions.",
    "limitation": "Offline fixed playback masks; no actual counterfactual cancellation of output, human microphone or UI acceptance. Dataset is development controls, never the human Carter reserve.",
    "sourceSha256": sha(ROOT / "src/baxy_mind/voice.py"), "captureCopySha256": sha(ROOT / "scratchpad/capture_split252.py"), "inputs": inputs, "confirmationInputs": final_inputs,
})

class Output:
    speaking = False
    available = False
    def start(self):
        pass

voice.create_speech_output = lambda _: Output()
decoder = voice.VoiceEngine(lambda _: None)
decoder.load()

class Ducker:
    def duck(self):
        return True
    def restore(self):
        return True

capture_path = ROOT / "scratchpad/capture_split252.py"
namespace = vars(voice)
exec(compile(capture_path.read_text(encoding="utf-8"), str(capture_path), "exec"), namespace)
voice.VoiceEngine._capture_loop = namespace["_capture_loop"]
confirmation_vad = voice.SileroVad()
results = []
for row in inputs:
    path = Path(row["privatePath"])
    assert sha(path) == row["sha256"]
    data = np.load(path)
    audio = data["clean"]
    audio = np.r_[np.zeros(64, np.float32), audio.ravel()][:-64].reshape(audio.shape)
    final_row = final_inputs[row["case"]]
    assert sha(Path(final_row["privatePath"])) == final_row["sha256"]
    final_data = np.load(final_row["privatePath"])
    confirmation_audio, guards, speaking = [final_data[key] for key in ["clean", "guards", "speaking"]]
    stop = threading.Event()
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
            frame = audio[self.reads]
            self.reads += 1
            return frame[:, None], False
    stream = Stream()
    class RecordedOutput(Output):
        @property
        def speaking(self):
            return bool(speaking[max(0, stream.reads - 1)])
    voice.create_speech_output = lambda _: RecordedOutput()
    voice._PcmCaptureStream = lambda *_: stream
    voice._looks_like_echo = lambda *_: bool(guards[stream.reads - 1])
    requests, events, cancellations = [], [], []
    engine = voice.VoiceEngine(lambda _: None, events.append)
    engine._mode = "direct"
    engine._pcm_inbox = queue.Queue()
    engine._ducker = Ducker()
    engine.probe = lambda: {}
    engine._vad = decoder._vad
    engine._vad.reset()
    engine._confirmation_vad = confirmation_vad
    confirmation_vad.reset()
    engine._confirmation_frame = lambda: confirmation_audio[stream.reads - 1]
    engine.cancel_speech = lambda: cancellations.append(stream.reads - 1)
    class Sink:
        def put_nowait(self, request):
            requests.append((stream.reads, request))
    engine._capture_loop(stop_event=stop, decode_queue=Sink(), capture_ready_event=threading.Event())
    assert not any(e.get("event") == "error" for e in events), events
    assert stream.reads == len(audio)
    segments, signals = [], {}
    for index, (end, request) in enumerate(requests):
        first = end * 512 - len(request.audio)
        assert np.array_equal(request.audio, audio.ravel()[first:end * 512])
        signals[f"segment{index}"] = request.audio
        segments.append({"firstSample": first, "lastSample": end * 512,
            "pcmSha256": hashlib.sha256(request.audio.tobytes()).hexdigest(),
            "text": decoder.transcribe_pcm(request.audio)})
    window_text = None
    if row.get("humanWindowSamples") is not None:
        first, last = row["humanWindowSamples"]
        window = audio.ravel()[first:last].copy()
        signals["humanWindow"] = window
        window_text = decoder.transcribe_pcm(window)
    target = PRIVATE / f'{row["case"]}-{row["backend"]}.npz'
    np.savez(target, **signals)
    result = {"case": row["case"], "backend": row["backend"], "human": row["human"],
        "referenceText": row["referenceText"], "segments": segments, "cancellations": cancellations,
        "humanWindowText": window_text, "privatePath": str(target), "sha256": sha(target)}
    results.append(result)
    save(OUT / "RESULTS.json", results)
    print(json.dumps({"case": row["case"], "backend": row["backend"],
        "segments": len(segments), "cancellations": len(cancellations), "windowText": window_text}, ensure_ascii=True), flush=True)
save(OUT / "COMPLETE.json", {"timelines": len(results), "fixedHumanWindows": 8,
    "segments": sum(len(r["segments"]) for r in results), "speexPriorParities": 0, "baseline237Reused": True, "exitCode": 0})
