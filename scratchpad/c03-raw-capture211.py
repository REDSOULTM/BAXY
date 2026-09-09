"""Paired default/RAW capture of one fixed physical playback, no product edits."""
from contextlib import ExitStack
import ctypes as C
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import uuid

import numpy as np
import psutil
import sounddevice as sd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind.voice_aec import AudioDucker, LoopbackReference, _com_apartment

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

class Guid(C.Structure):
    _fields_ = [("data", C.c_ubyte * 16)]

class Effect(C.Structure):
    _fields_ = [("id", Guid), ("canSetState", C.c_int32), ("state", C.c_int32)]

def method(pointer, index, result, *args):
    table = C.cast(pointer, C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(result, C.c_void_p, *args)(table[index])

def stream_effects(stream):
    """Read actual PortAudio client's effects, never mutate the COM object."""
    library = C.CDLL(sd._libname)
    get_client = library.PaWasapi_GetAudioClient
    get_client.argtypes = [C.c_void_p, C.POINTER(C.c_void_p), C.c_int]
    get_client.restype = C.c_int
    client = C.c_void_p()
    result = get_client(int(sd._ffi.cast("uintptr_t", stream._ptr)), C.byref(client), 0)
    if result != 0:
        raise RuntimeError(f"get_audio_client:{result}")
    iid = Guid.from_buffer_copy(uuid.UUID("4460b3ae-4b44-4527-8676-7548a8acd260").bytes_le)
    manager = C.c_void_p()
    hr = method(client, 14, C.c_int32, C.POINTER(Guid), C.POINTER(C.c_void_p))(
        client, C.byref(iid), C.byref(manager))
    if hr < 0:
        raise RuntimeError(f"get_effects_manager:{hr & 0xffffffff:08x}")
    try:
        effects = C.POINTER(Effect)()
        count = C.c_uint32()
        hr = method(manager, 5, C.c_int32, C.POINTER(C.POINTER(Effect)), C.POINTER(C.c_uint32))(
            manager, C.byref(effects), C.byref(count))
        if hr < 0:
            raise RuntimeError(f"get_effects:{hr & 0xffffffff:08x}")
        try:
            return [{"id": str(uuid.UUID(bytes_le=bytes(effects[i].id.data))),
                     "state": effects[i].state, "canSetState": bool(effects[i].canSetState)}
                    for i in range(count.value)]
        finally:
            C.windll.ole32.CoTaskMemFree.argtypes = [C.c_void_p]
            C.windll.ole32.CoTaskMemFree(effects)
    finally:
        method(manager, 2, C.c_ulong)(manager)
    # client is borrowed from PortAudio and must not be released here.

def main():
    assert "--physical-output" in sys.argv
    assert not any(p.info["name"] in {"Baxy.exe", "llama-server.exe", "piper.exe"}
                   for p in psutil.process_iter(["name"]))
    out = ROOT / "artifacts/comprobaciones/C03/astra-raw-capture211"
    private = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-raw-capture211-private"
    out.mkdir(exist_ok=False)
    private.mkdir(exist_ok=False)
    source = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-sidecar187-private/generated187.npz"
    assert digest(source) == "d072466450c409a3d74b61ff8c0a21dce39d68b709947da622c66907fda95f1a"
    generated = np.load(source)
    audio = np.zeros(30 * 22050, np.float32)
    starts = [2, 9, 16, 23]
    intervals = []
    for i, start in enumerate(starts):
        clip = generated[f"audio{i}"]
        audio[start * 22050:start * 22050 + len(clip)] = clip
        intervals.append([start, start + len(clip) / 22050])
    save(out / "PREREG.json", {
        "utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": digest(Path(__file__)),
        "sourceSha256": digest(source), "playbackSha256": hashlib.sha256(audio.tobytes()).hexdigest(),
        "method": "Simultaneous default/RAW 16k mono512 WASAPI callbacks; same device, autoconvert, ADC anchoring and product loopback4512. One fixed30s playback of four original187 Piper clips at seconds2/9/16/23. No live cancel/filter/ASR/model/wake.",
        "comparison": "Capture actual per-stream APO effects before starting; require normal AEC ON and RAW no AEC. Analyze both captured inputs with unchanged Speex/VAD/guard offline. No threshold or gain sweep.",
        "limitation": "Pure playback echo only; no simultaneous physical human voice, no acceptance, no causal claim about historical183 yet.",
        "levelScalar": .30, "maximumSeconds": 40, "intervalsSeconds": intervals,
        "sourceCaptureSha256": digest(ROOT / "src/baxy_mind/voice_capture.py"),
        "sourceLoopbackSha256": digest(ROOT / "src/baxy_mind/voice_aec.py"),
        "portaudioSha256": digest(Path(sd._libname)),
    })
    stop = threading.Event()
    done = threading.Event()
    frames = queue.Queue(256)
    errors = []
    recordings = {name: {"microphone": [], "reference": [], "timing": []} for name in ["default", "raw"]}
    cursors = {name: None for name in recordings}
    playback = {}
    effects = {}
    def callback(name):
        def receive(data, count, timing, status):
            if status or count != 512 or data.shape != (512, 1):
                errors.append(f"{name}:callback:{status}:{count}")
                stop.set()
                return
            try:
                frames.put_nowait((name, data[:, 0].copy(), float(timing.inputBufferAdcTime)))
            except queue.Full:
                errors.append(f"{name}:queue_full")
                stop.set()
        return receive
    def play(device):
        try:
            with _com_apartment():
                with sd.OutputStream(device=device, samplerate=22050, channels=1, dtype="float32",
                                     extra_settings=sd.WasapiSettings(auto_convert=True)) as stream:
                    playback.update(startMonotonic=time.monotonic(), streamTime=stream.time, latency=stream.latency)
                    for first in range(0, len(audio), 662):
                        if stop.is_set():
                            break
                        if stream.write(audio[first:first + 662]):
                            raise RuntimeError("playback_underflow")
                    playback["endMonotonic"] = time.monotonic()
        except Exception as error:
            errors.append(f"playback:{error!r}")
            stop.set()
        finally:
            done.set()

    with _com_apartment():
        endpoint = AudioDucker._endpoint()
        before = {"levelScalar": float(endpoint.GetMasterVolumeLevelScalar()), "muted": bool(endpoint.GetMute())}
        save(out / "AUDIO_SETUP.json", {"before": before, "testLevelScalar": .30})
        loopback = LoopbackReference()
        worker = None
        try:
            api = next(item for item in sd.query_hostapis() if item["name"] == "Windows WASAPI")
            with ExitStack() as stack:
                streams = []
                for name in recordings:
                    options = sd.WasapiSettings(auto_convert=True)
                    if name == "raw":
                        options._streaminfo.streamOption = 1
                    stream = sd.InputStream(device=api["default_input_device"], samplerate=16000,
                        channels=1, dtype="float32", blocksize=512, extra_settings=options, callback=callback(name))
                    stack.callback(stream.close)
                    effects[name] = stream_effects(stream)
                    streams.append(stream)
                save(out / "ACTUAL_STREAM_EFFECTS.json", effects)
                aec = "6f64adbe-8211-11e2-8c70-2c27d7f001fa"
                assert any(e["id"] == aec and e["state"] == 1 for e in effects["default"])
                assert not any(e["id"] == aec and e["state"] == 1 for e in effects["raw"])
                assert loopback.start(), loopback.last_error
                endpoint.SetMasterVolumeLevelScalar(.30, None)
                endpoint.SetMute(0, None)
                for stream in streams:
                    stream.start()
                worker = threading.Thread(target=play, args=(api["default_output_device"],), daemon=False)
                worker.start()
                start = time.monotonic()
                print("Paired capture active; fixed30s playback; restoration in finally.", flush=True)
                while not stop.is_set() and time.monotonic() - start < 35:
                    if done.is_set() and time.monotonic() - playback.get("endMonotonic", start) > 2:
                        break
                    try:
                        name, microphone, adc = frames.get(timeout=.1)
                    except queue.Empty:
                        continue
                    if cursors[name] is None:
                        cursors[name] = loopback.sample_index(adc, stop)
                    cursors[name] += 512
                    reference = loopback.window_at(cursors[name], 4512, stop)
                    recordings[name]["microphone"].append(microphone)
                    recordings[name]["reference"].append(reference)
                    recordings[name]["timing"].append([adc, time.monotonic(), cursors[name]])
                if not done.is_set():
                    errors.append("playback_not_complete")
        except Exception as error:
            errors.append(repr(error))
            raise
        finally:
            stop.set()
            if worker is not None:
                worker.join(timeout=5)
            loopback_stopped = loopback.stop()
            endpoint.SetMasterVolumeLevelScalar(before["levelScalar"], None)
            endpoint.SetMute(int(before["muted"]), None)
            after = {"levelScalar": float(endpoint.GetMasterVolumeLevelScalar()), "muted": bool(endpoint.GetMute())}
            rows = []
            for name, arrays in recordings.items():
                path = private / f"{name}.npz"
                np.savez(path, **{key: np.asarray(value) for key, value in arrays.items()})
                rows.append({"mode": name, "frames": len(arrays["microphone"]), "sha256": digest(path)})
            result = {"before": before, "after": after, "restoredExactly": before == after,
                "errors": errors, "streams": rows, "playback": playback, "loopbackError": loopback.last_error,
                "loopbackStopped": loopback_stopped, "workerStopped": worker is None or not worker.is_alive()}
            save(out / "RESULTS.json", result)
            print(json.dumps(result), flush=True)
    assert not errors and before == after and loopback_stopped
    save(out / "COMPLETE.json", {"utc": datetime.now(timezone.utc).isoformat(), "exitCode": 0})

if __name__ == "__main__":
    main()
