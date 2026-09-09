"""Observe actual playback and barge-in while varying only the microphone mode."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import sys
import threading
import time

import psutil

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
sys.stdout.reconfigure(encoding='utf-8')
from baxy_mind.voice import VoiceEngine
from baxy_mind.voice_output import NeuralSpeechOutput
out = root / 'artifacts/comprobaciones/C03/astra-voice139'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-voice139-private'
assert (out / 'AUDIO_READY.json').exists()
assert not any(p.info['name'] in {'Baxy.exe', 'llama-server.exe'} for p in psutil.process_iter(['name']))
prereg = json.loads((out / 'PREREG.json').read_text(encoding='utf-8'))
def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
assert all(sha(root / p) == digest for p, digest in prereg['sources'].items())
lock = threading.Lock()
events = []
transcripts = []
started = threading.Event()
finished = threading.Event()
phase = 'load'
def event(payload):
    with lock:
        row = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'monotonic': time.monotonic(),
               'phase': phase, **payload}
        events.append(row)
        with (out / 'EVENTS.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    if payload.get('event') == 'state' and payload.get('speaking') is True:
        started.set()
    elif payload.get('event') == 'state' and payload.get('speaking') is False and started.is_set():
        finished.set()
def transcript(text):
    transcripts.append({'phase': phase, 'text': text})
    (private / 'transcripts.json').write_text(json.dumps(transcripts, ensure_ascii=False, indent=2), encoding='utf-8')

import numpy as np
import sounddevice as sd
import baxy_mind.voice as voice_module
import baxy_mind.voice_aec as aec_module
original_stream = sd.InputStream
original_process = voice_module.EchoCanceller.process
original_vad = voice_module.SileroVad.process
original_resample = aec_module._resample
reads, processes, vads, callbacks = [], [], [], []
raw_blocks, clean_blocks, references, loop_blocks = [], [], [], []

class ObservedStream:
    def __init__(self, *args, **kwargs):
        self.inner = original_stream(*args, **kwargs)
    def __getattr__(self, name):
        return getattr(self.inner, name)
    def __enter__(self):
        self.inner.__enter__()
        return self
    def __exit__(self, *args):
        return self.inner.__exit__(*args)
    def read(self, samples):
        result = self.inner.read(samples)
        loop = engine._loopback._stream
        reads.append({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'monotonic':time.monotonic(), 'micTime':self.inner.time,
                      'micLatency':self.inner.latency, 'micReadAvailable':self.inner.read_available,
                      'loopTime':loop.get_time(), 'loopLatency':loop.get_input_latency()})
        return result

def observe_process(self, mic, reference):
    result = original_process(self, mic, reference)
    processes.append({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'readIndex':len(reads)-1, 'callbacksSeen':len(callbacks)})
    raw_blocks.append(mic.copy()); references.append(reference.copy()); clean_blocks.append(result[0].copy())
    return result

def observe_vad(self, frame):
    result = original_vad(self, frame)
    vads.append({'probability':result, 'rms':float(np.sqrt(np.mean(frame**2)))})
    return result

def observe_resample(audio, rate):
    result = original_resample(audio, rate)
    callbacks.append({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'monotonic':time.monotonic(), 'samples':len(result)})
    loop_blocks.append(result.copy())
    return result

sd.InputStream = ObservedStream
voice_module.EchoCanceller.process = observe_process
voice_module.SileroVad.process = observe_vad
aec_module._resample = observe_resample

engine = VoiceEngine(transcript, event)
assert isinstance(engine._output, NeuralSpeechOutput)
rows = []
try:
    engine.load()
    for phase in prereg['phases']:
        if phase == 'direct':
            assert engine.start('direct'), engine.last_error
        elif phase == 'off-after':
            assert engine.stop(timeout=10), engine.last_error
        time.sleep(1)
        started.clear(); finished.clear()
        begin = len(events)
        request_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        request_time = time.monotonic()
        assert engine.speak(prereg['text'])
        assert started.wait(15), engine._output.last_error
        assert finished.wait(15), engine._output.last_error
        time.sleep(1)
        with lock:
            observed = list(events[begin:])
        talking = [x for x in observed if x.get('event') == 'state' and x.get('speaking') is True]
        silent = [x for x in observed if x.get('event') == 'state' and x.get('speaking') is False]
        row = {'phase': phase, 'requestUtc': request_utc, 'elapsedSeconds': time.monotonic() - request_time,
               'speakingSeconds': silent[0]['monotonic'] - talking[0]['monotonic'],
               'bargeInEvents': sum(x.get('event') == 'barge_in' for x in observed),
               'outputError': engine._output.last_error, 'voice': engine._output.voice_name,
               'voiceSha256': engine._output.voice_sha256, 'status': engine.status()}
        rows.append(row)
        (out / 'RESULTS.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in row.items() if k != 'status'}, ensure_ascii=False), flush=True)
finally:
    engine.shutdown()
    sd.InputStream = original_stream
    voice_module.EchoCanceller.process = original_process
    voice_module.SileroVad.process = original_vad
    aec_module._resample = original_resample
    np.savez_compressed(private / 'timing139.npz', raw=raw_blocks, clean=clean_blocks,
                        reference=references, loop=np.concatenate(loop_blocks) if loop_blocks else np.array([]))
    (private / 'timing139.json').write_text(json.dumps({'reads':reads,'processes':processes,
        'vads':vads,'callbacks':callbacks},indent=2),encoding='utf-8')
    print(json.dumps({'reads':len(reads),'processes':len(processes),'callbacks':len(callbacks)}),flush=True)
    (out / 'STOP_AUDIO').touch(exist_ok=False)
assert all(sha(root / p) == digest for p, digest in prereg['sources'].items())
print('Voice engine shutdown completed; capture stop requested.', flush=True)
