"""Before/after segmentation on eight fixed human Speex controls from213."""
import hashlib
import importlib.util
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
import baxy_mind.voice as current

original_guard = current._looks_like_echo

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-human226"
PRIVATE_ROOT = Path(os.environ["LOCALAPPDATA"]) / "BAXY"
PRIVATE = PRIVATE_ROOT / "C03-human226-private"
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)

def read(p):
    return json.loads(p.read_text(encoding="utf-8"))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

baseline_path = BASE / "astra-source220-snapshot/src/baxy_mind/voice.py"
assert sha(baseline_path) == read(BASE / "astra-source220-snapshot/FILES.json")["src/baxy_mind/voice.py"]
spec = importlib.util.spec_from_file_location("baxy_mind.voice_baseline226", baseline_path)
baseline = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = baseline
spec.loader.exec_module(baseline)
inputs = [r for r in read(BASE / "astra-raw-human213/RESULTS.json") if r["condition"] in {"near_speex", "raw_speex"}]
humans = read(BASE / "astra-human195/DOWNLOADS.json")
capture = read(BASE / "astra-raw-capture211/RESULTS.json")
raw_path = PRIVATE_ROOT / "C03-raw-capture211-private/raw.npz"
assert sha(raw_path) == next(r["sha256"] for r in capture["streams"] if r["mode"] == "raw")
raw = np.load(raw_path)
microphone, reference, timing = [raw[k] for k in ["microphone", "reference", "timing"]]
origin = capture["playback"]["streamTime"] + capture["playback"]["latency"]
intervals = np.asarray(read(BASE / "astra-raw-capture211/PREREG.json")["intervalsSeconds"]) + origin
mask_time = timing[:, 0] - .032
speaking_mask = np.any((mask_time[:, None] >= intervals[None, :, 0]) & (mask_time[:, None] < intervals[None, :, 1]), axis=1)
save(OUT / "PREREG.json", {
    "method": "Eight exact213 full cleaned timelines: four195 humans near_speex with speakingFalse and raw_speex with fixed212 scheduled speaking mask. Baseline220 vs source225 through their actual capture segmentation, fresh-reset Silero and actual guard on reconstructed213 delayed raw/reference pairs. Same installed baxy.2 model shared for native decoding; no hints, normalization, threshold or gain changes.",
    "criterion": "Compare every segment/sample range/transcription/cancellation. Preserve human content; publish any differences and errors instead of counting mere execution as semantic passes.",
    "limitation": "Constructed human+physical echo with fixed playback mask, not simultaneous physical human or actual counterfactual speaker cancellation. ADC mask approximate at playback boundaries as212.",
    "scriptSha256": sha(Path(__file__)), "baselineSha256": sha(baseline_path),
    "currentSha256": sha(ROOT / "src/baxy_mind/voice.py"), "rawCaptureSha256": sha(raw_path),
    "inputs": [{k: r[k] for k in ["human", "condition", "gain", "onset", "sha256"]} for r in inputs],
})

class Output:
    available = False
    speaking = False
    def start(self):
        pass

current.create_speech_output = lambda _: Output()
decoder = current.VoiceEngine(lambda _: None)
decoder.load()

class Ducker:
    def duck(self):
        return True
    def restore(self):
        return True

results = []
for row in inputs:
    path = PRIVATE_ROOT / "C03-raw-human213-private" / f'h{row["human"]}-{row["condition"]}.npz'
    assert sha(path) == row["sha256"]
    audio = np.load(path)["clean"]
    human = humans[row["human"]]
    assert sha(Path(human["asset"])) == human["sha256"]
    rate, original = wavfile.read(human["asset"])
    assert rate == 16000
    near = np.zeros(microphone.size, np.float32)
    near[row["onset"]:row["onset"] + len(original)] = original * row["gain"]
    mixed = row["condition"] == "raw_speex"
    incoming = near.reshape(microphone.shape) + (microphone if mixed else 0)
    ref = reference if mixed else np.zeros_like(reference)
    speaking = speaking_mask if mixed else np.zeros(len(audio), bool)
    variants = []
    for name, module in [("before220", baseline), ("after225", current)]:
        event = threading.Event()
        class Stream:
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
        stream = Stream()
        class RecordedOutput(Output):
            @property
            def speaking(self):
                return bool(speaking[max(0, stream.reads - 1)])
        module.create_speech_output = lambda _: RecordedOutput()
        module._PcmCaptureStream = lambda *_: stream
        def recorded_guard(_mic, _ref):
            i = stream.reads - 1
            return original_guard(incoming[i - 1] * 32768 if i else np.zeros(512), ref[i - 1] if i else np.zeros(4512))
        module._looks_like_echo = recorded_guard
        requests, events, cancellations = [], [], []
        engine = module.VoiceEngine(lambda _: None, events.append)
        engine._mode = "direct"
        engine._pcm_inbox = queue.Queue()
        engine._ducker = Ducker()
        engine.probe = lambda: {}
        engine._vad = decoder._vad
        engine._vad.reset()
        engine.cancel_speech = lambda: cancellations.append(stream.reads - 1)
        class Sink:
            def put_nowait(self, request):
                requests.append((stream.reads, request))
        engine._capture_loop(stop_event=event, decode_queue=Sink(), capture_ready_event=threading.Event())
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
        target = PRIVATE / f'h{row["human"]}-{row["condition"]}-{name}.npz'
        np.savez(target, **signals)
        variants.append({"source": name, "segments": segments, "cancellations": cancellations,
            "privatePath": str(target), "sha256": sha(target)})
    result = {"human": row["human"], "condition": row["condition"], "reference": human["rawTranscription"],
        "variants": variants, "segmentsIdentical": variants[0]["segments"] == variants[1]["segments"],
        "cancellationsIdentical": variants[0]["cancellations"] == variants[1]["cancellations"]}
    results.append(result)
    save(OUT / "RESULTS.json", results)
    print(json.dumps({k: result[k] for k in ["human", "condition", "segmentsIdentical", "cancellationsIdentical"]}), flush=True)
save(OUT / "COMPLETE.json", {"cases": len(results), "identicalSegments": sum(r["segmentsIdentical"] for r in results),
    "identicalCancellations": sum(r["cancellationsIdentical"] for r in results), "exitCode": 0})
