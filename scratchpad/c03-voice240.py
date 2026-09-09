"""Bounded physical product voice session: RAW, Speex, VAD, Piper and ASR."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time

import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import baxy_mind.voice as voice
from baxy_mind.voice_aec import AudioDucker, _com_apartment
from baxy_mind.voice_capture import WasapiCaptureStream
from baxy_mind.voice_output import NeuralSpeechOutput
from baxy_mind.piper_tts import PiperEngine
from dtln_stream182 import EchoCanceller as Dtln

class CandidateCanceller(Dtln):
    def __init__(self):
        super().__init__(512)

voice.EchoCanceller = CandidateCanceller
voice.resolve_echo_canceller_library = lambda: Path("D:/BAXYRuntime/experiments/voice/dtln180")

OUT = ROOT / "artifacts/comprobaciones/C03/astra-voice240"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-voice240-private"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    assert "--physical-output" in sys.argv
    assert not any(p.info["name"] in {"Baxy.exe", "llama-server.exe", "piper.exe"}
                   for p in psutil.process_iter(["name"]))
    assert importlib.metadata.version("sherpa-onnx") == "1.13.4+baxy.2"
    OUT.mkdir(exist_ok=False)
    PRIVATE.mkdir(exist_ok=False)
    helper = ROOT / "scratchpad/c03-raw-capture211.py"
    spec = importlib.util.spec_from_file_location("capture211", helper)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    texts = json.loads((ROOT / "artifacts/comprobaciones/C03/astra-sidecar187/PREREG.json").read_text(encoding="utf-8"))["texts"]
    save(OUT / "PREREG.json", {
        "utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": sha(Path(__file__)),
        "method": "Source230 VoiceEngine direct session with experimental DTLN512 binding182/180 in place of Speex, actual RAW capture/Silero/Piper/installed baxy.2; no product source, dependency lock, registration or wake changes; four fixed187 TTS texts, one per10seconds after2s warmup. No LLM/App/UI/wake seam, no alternative decoder or thresholds. Record exact microphone/reference/clean with bounded observer after actual Speex process, and VAD/guard decisions.",
        "criterion": "Actual WASAPI client no adaptive AEC/NS, ready capture, four TTS generation/admission results, actual barge_in/transcript/error counts, exact volume restoration and stopped workers. Zero false interruptions alone is not voice acceptance.",
        "limitation": "Pure speaker playback echo; no controlled simultaneous physical human speech. Direct mode is an existing product mode; this does not validate wake. Per-frame observer affects scheduling.",
        "texts": texts, "maximumCaptureSeconds": 60, "levelScalar": .30,
        "sourceFiles": {str(p): sha(ROOT / p) for p in [
            "src/baxy_mind/voice.py", "src/baxy_mind/voice_capture.py", "src/baxy_mind/voice_aec.py",
            "src/baxy_mind/speex_aec.py", "src/baxy_mind/voice_output.py", "src/baxy_mind/piper_tts.py"]},
        "probeSha256": sha(helper), "adapterSha256": sha(ROOT / "scratchpad/dtln_stream182.py"), "candidateModels": json.loads((ROOT / "artifacts/comprobaciones/C03/astra-dtln180/DOWNLOADS.json").read_text(encoding="utf-8")),
    })
    capacity = 2000
    near = np.empty((capacity, 512), np.float32)
    reference = np.empty((capacity, 4512), np.int16)
    clean = np.empty((capacity, 512), np.float32)
    observations = np.full((capacity, 6), np.nan, np.float64)
    count = 0
    owner = None
    effects = []
    generated = []
    states = []
    events = []
    transcripts = []
    admissions = []
    errors = []
    engine = None
    original_process = voice.EchoCanceller.process
    original_vad = voice.SileroVad.process
    original_guard = voice._looks_like_echo
    original_enter = WasapiCaptureStream.__enter__
    original_generate = PiperEngine.generate
    original_state = NeuralSpeechOutput._set_speaking

    def observe_process(self, microphone, history):
        nonlocal count, owner
        owner = threading.get_ident()
        begin = time.perf_counter()
        result = original_process(self, microphone, history)
        after = time.perf_counter()
        i = count
        if i >= capacity:
            raise RuntimeError("diagnostic_capacity_exceeded")
        near[i], reference[i], clean[i] = microphone, history, result[0]
        observations[i] = [time.monotonic(), (after - begin) * 1000, 0, float(engine.speaking), np.nan, -1]
        count += 1
        observations[i, 2] = (time.perf_counter() - after) * 1000
        return result

    def observe_vad(self, frame):
        result = original_vad(self, frame)
        if count and threading.get_ident() == owner:
            observations[count - 1, 4] = result
        return result

    def observe_guard(microphone, history):
        result = original_guard(microphone, history)
        if count and threading.get_ident() == owner:
            observations[count - 1, 5] = float(result)
        return result

    def observe_enter(self):
        result = original_enter(self)
        try:
            actual = probe.stream_effects(self._stream)
            effects.append(actual)
            forbidden = {"6f64adbe-8211-11e2-8c70-2c27d7f001fa", "6f64adbf-8211-11e2-8c70-2c27d7f001fa"}
            assert not any(e["id"] in forbidden and e["state"] == 1 for e in actual)
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise
        return result

    def observe_generate(self, text, cancelled=None):
        result = original_generate(self, text, cancelled)
        generated.append((result.copy(), {"text": text, "sampleRate": self.sample_rate,
            "model": str(self.model_path), "time": time.monotonic()}))
        return result

    def observe_state(self, value):
        result = original_state(self, value)
        states.append({"time": time.monotonic(), "speaking": value, "changed": result})
        return result

    voice.EchoCanceller.process = observe_process
    voice.SileroVad.process = observe_vad
    voice._looks_like_echo = observe_guard
    WasapiCaptureStream.__enter__ = observe_enter
    PiperEngine.generate = observe_generate
    NeuralSpeechOutput._set_speaking = observe_state
    with _com_apartment():
        endpoint = AudioDucker._endpoint()
        before = {"levelScalar": float(endpoint.GetMasterVolumeLevelScalar()), "muted": bool(endpoint.GetMute())}
        save(OUT / "AUDIO_SETUP.json", {"before": before, "testLevelScalar": .30})
        try:
            engine = voice.VoiceEngine(
                lambda text: transcripts.append({"time": time.monotonic(), "text": text}),
                lambda event: events.append({"time": time.monotonic(), **event}),
            )
            assert isinstance(engine._output, NeuralSpeechOutput)
            engine.load()
            assert engine._output.available, engine._output.last_error
            endpoint.SetMasterVolumeLevelScalar(.30, None)
            endpoint.SetMute(0, None)
            assert engine.start("direct"), engine.last_error
            assert engine._aec_active
            start = time.monotonic()
            print("Physical RAW/DTLN512 diagnostic direct session ready; four fixed TTS controls.", flush=True)
            for index, text in enumerate(texts):
                deadline = start + 2 + index * 10
                while time.monotonic() < deadline:
                    time.sleep(.05)
                admitted = engine.speak(text)
                admissions.append({"index": index, "time": time.monotonic(), "admitted": admitted})
                assert admitted
            while time.monotonic() < start + 42:
                time.sleep(.05)
            save(PRIVATE / "STATUS.json", engine.status())
        except BaseException as error:
            errors.append(repr(error))
            raise
        finally:
            if engine is not None:
                engine.shutdown()
            endpoint.SetMasterVolumeLevelScalar(before["levelScalar"], None)
            endpoint.SetMute(int(before["muted"]), None)
            after = {"levelScalar": float(endpoint.GetMasterVolumeLevelScalar()), "muted": bool(endpoint.GetMute())}
            np.savez(PRIVATE / "tap240.npz", microphone=near[:count], reference=reference[:count],
                clean=clean[:count], observations=observations[:count])
            np.savez(PRIVATE / "generated240.npz", **{f"audio{i}": item[0] for i, item in enumerate(generated)})
            save(PRIVATE / "generated240.json", [item[1] for item in generated])
            save(PRIVATE / "EVENTS.json", {"events": events, "transcripts": transcripts, "states": states})
            workers = {name: bool(getattr(engine, name, None) and getattr(engine, name).is_alive())
                for name in ["_capture_worker", "_decode_worker", "_streaming_worker", "_acoustic_wake_worker"]} if engine else {}
            output_worker = getattr(engine._output, "_worker", None) if engine else None
            result = {"frames": count, "audioSeconds": count * .032, "effects": effects,
                "admissions": admissions, "generated": len(generated), "before": before, "after": after,
                "restoredExactly": before == after, "workersAlive": workers,
                "outputWorkerAlive": bool(output_worker and output_worker.is_alive()),
                "bargeInCount": sum(e["event"] == "barge_in" for e in events),
                "transcriptCount": len(transcripts), "voiceErrors": [e for e in events if e["event"] == "error"],
                "driverErrors": errors, "lastError": engine.last_error if engine else None,
                "wakeBackend": engine._wake_backend if engine else None,
                "wakeError": engine._wake_error if engine else None,
                "columns": ["monotonic", "dspMs", "copyMs", "speaking", "vadProbability", "echoGuard"],
                "privateFiles": [{"path": str(p), "sha256": sha(p)} for p in PRIVATE.iterdir() if p.is_file()]}
            save(OUT / "RESULTS.json", result)
            print(json.dumps({k: v for k, v in result.items() if k not in {"privateFiles", "admissions", "voiceErrors"}}), flush=True)
    assert before == after and not errors and not any(workers.values()) and not result["outputWorkerAlive"]
    assert not result["voiceErrors"] and len(generated) == 4 and count > 1000
    save(OUT / "COMPLETE.json", {"exitCode": 0, "criterion": "Diagnostic completed, quality separately adjudicated."})

if __name__ == "__main__":
    main()
