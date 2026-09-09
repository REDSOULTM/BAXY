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
out = root / 'artifacts/comprobaciones/C03/astra-voice134'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-voice134-private'
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
import baxy_mind.voice as voice_module
from speex_stream134 import SpeexStream
original_vad = voice_module.SileroVad.process
original_echo = voice_module._looks_like_echo
pipeline = None
shadow_vad = None
shadow_floor = .002
shadow_count = 0
previous_pair = (np.zeros(512), np.zeros(4512))
current_pair = previous_pair
observations = []
raw_blocks, clean_blocks, references = [], [], []

def process_candidate(self, frame):
    global previous_pair, current_pair, shadow_floor, shadow_count
    raw = frame.copy()
    history = engine._loopback.latest(4512)
    begin = time.perf_counter()
    clean = pipeline.process(raw, history[-512:])
    cost = time.perf_counter() - begin
    probability = original_vad(shadow_vad, raw)
    rms = float(np.sqrt(np.mean(raw**2)))
    if probability < .5:
        shadow_floor = .98*shadow_floor + .02*rms
    shadow_barge = False
    shadow_echo = None
    if probability >= .5 and engine.speaking:
        shadow_echo = original_echo(raw*32768, history)
        if shadow_echo:
            shadow_count = 0
        elif rms >= max(.004, shadow_floor*1.8):
            shadow_count += 1
            shadow_barge = shadow_count == 3
        else:
            shadow_count = 0
    current_pair = previous_pair
    previous_pair = (raw*32768, history)
    frame[:] = clean
    result = original_vad(self, frame)
    observations.append({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         'rawProbability': probability, 'cleanProbability': result,
                         'rawRms': rms, 'cleanRms': float(np.sqrt(np.mean(clean**2))),
                         'shadowEcho': shadow_echo, 'shadowBarge': shadow_barge,
                         'aecSeconds': cost})
    raw_blocks.append(raw); clean_blocks.append(clean); references.append(history)
    return result

def delayed_echo(_microphone, _reference):
    return original_echo(*current_pair)

voice_module.SileroVad.process = process_candidate
voice_module._looks_like_echo = delayed_echo

engine = VoiceEngine(transcript, event)
assert isinstance(engine._output, NeuralSpeechOutput)
rows = []
try:
    engine.load()
    pipeline = SpeexStream('D:/BAXYRuntime/experiments/voice/speexdsp129/build/speexdsp.dll')
    shadow_vad = voice_module.SileroVad()
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
    voice_module.SileroVad.process = original_vad
    voice_module._looks_like_echo = original_echo
    if pipeline:
        pipeline.close()
    np.savez_compressed(private / 'candidate134.npz', raw=raw_blocks, clean=clean_blocks, reference=references)
    (private / 'candidate134.json').write_text(json.dumps(observations, indent=2), encoding='utf-8')
    print(json.dumps({'frames':len(observations), 'shadowBargeEvents':sum(r['shadowBarge'] for r in observations)}), flush=True)
    (out / 'STOP_AUDIO').touch(exist_ok=False)
assert all(sha(root / p) == digest for p, digest in prereg['sources'].items())
print('Voice engine shutdown completed; capture stop requested.', flush=True)
