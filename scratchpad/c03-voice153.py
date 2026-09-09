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
out = root / 'artifacts/comprobaciones/C03/astra-voice153'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-voice153-private'
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
from baxy_mind.piper_tts import PiperEngine
original_generate = PiperEngine.generate
generated = []
def observed_generate(self, text, cancelled=None):
    result = original_generate(self, text, cancelled)
    generated.append((phase, self.sample_rate, result.copy()))
    return result
PiperEngine.generate = observed_generate
engine = VoiceEngine(transcript, event)
assert isinstance(engine._output, NeuralSpeechOutput)
rows = []
try:
    engine.load()
    for phase in prereg['phases']:
        if phase.startswith('direct'):
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
        assert engine.stop(timeout=10), engine.last_error
        rows.append(row)
        (out / 'RESULTS.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in row.items() if k != 'status'}, ensure_ascii=False), flush=True)
finally:
    engine.shutdown()
    (out / 'STOP_AUDIO').touch(exist_ok=False)
assert all(sha(root / p) == digest for p, digest in prereg['sources'].items())
print('Voice engine shutdown completed; capture stop requested.', flush=True)

generated_index=[]
for label, rate, pcm in generated:
    target=private/(label+'-generated.npy')
    np.save(target,pcm)
    generated_index.append({'phase':label,'sampleRate':rate,'samples':len(pcm),'seconds':len(pcm)/rate,
                            'privatePath':str(target),'sha256':sha(target)})
(out/'GENERATED_INDEX.json').write_text(json.dumps(generated_index,indent=2),encoding='utf-8')
