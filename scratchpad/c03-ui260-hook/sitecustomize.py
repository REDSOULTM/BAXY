"""Read-only voice observations for actual desktop260; never inject events."""
import hashlib
import itertools
import json
import os
from pathlib import Path
import threading
import time

import numpy as np
from baxy_mind.voice import VoiceEngine
from baxy_mind.webrtc_aec import EchoCanceller
from baxy_mind.piper_tts import PiperEngine

PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-ui260-private'
PRIVATE.mkdir(parents=True, exist_ok=True)
lock = threading.Lock()
sequence = itertools.count()
sessions = {}
original_emit = VoiceEngine._emit
original_generate = PiperEngine.generate
original_process = EchoCanceller.process
original_close = EchoCanceller.close

def log(value):
    with lock, (PRIVATE / 'voice-events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'time': time.monotonic(), 'pid': os.getpid(), **value}, ensure_ascii=False)+'\n')

def emit(self, event, **payload):
    log({'event': event, **payload})
    return original_emit(self, event, **payload)

def generate(self, text, cancelled=None):
    result = original_generate(self, text, cancelled)
    path = PRIVATE / f'piper-{os.getpid()}-{next(sequence)}.npy'
    np.save(path, result)
    log({'event':'piper_generated', 'text':text, 'sampleRate':self.sample_rate,
         'samples':int(result.size), 'model':str(self.model_path), 'path':str(path),
         'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    return result

def process(self, microphone, reference):
    started = time.perf_counter()
    result = original_process(self, microphone, reference)
    elapsed = (time.perf_counter()-started)*1000
    row = sessions.setdefault(id(self), {'frames':0, 'dspTotalMs':0, 'dspMaxMs':0,
        'micMeanSquareSum':0, 'referenceMeanSquareSum':0, 'recognitionMeanSquareSum':0,
        'confirmationMeanSquareSum':0, 'nativeSha256':self.sha256})
    row['frames'] += 1
    row['dspTotalMs'] += elapsed
    row['dspMaxMs'] = max(row['dspMaxMs'], elapsed)
    for key, audio in [('mic',microphone),('reference',reference),('recognition',result.recognition),('confirmation',result.confirmation)]:
        row[key+'MeanSquareSum'] += float(np.mean(np.asarray(audio,np.float64)**2))
    if row['frames'] % 100 == 0:
        log({'event':'aec_observation', **row})
    return result

def close(self):
    result = original_close(self)
    row = sessions.pop(id(self), None)
    if row is not None:
        log({'event':'aec_closed', **row})
    return result

VoiceEngine._emit = emit
PiperEngine.generate = generate
EchoCanceller.process = process
EchoCanceller.close = close
log({'event':'observation_hook_loaded'})
