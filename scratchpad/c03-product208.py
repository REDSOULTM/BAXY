"""Use the installed dependency and real VoiceEngine on frozen human PCM."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import os
import sys
import time

import numpy as np
import psutil
from scipy.io import wavfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'src'))
import baxy_mind.voice as voice
import sherpa_onnx

base = root/'artifacts/comprobaciones/C03'
out = base/'astra-product208'
out.mkdir(exist_ok=False)
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def save(name, value):
    (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
native = Path(sys.modules['sherpa_onnx.lib._sherpa_onnx'].__file__)
versions = {name: importlib.metadata.version(name) for name in ['sherpa-onnx','sherpa-onnx-core']}
assert versions == {'sherpa-onnx':'1.13.4+baxy.1','sherpa-onnx-core':'1.13.4'}
assert 'site-packages' in str(native)
expected = read(base/'astra-greedy203/RESULTS.json')
inputs = read(base/'astra-segment201-retry/RESULTS.json')
humans = read(base/'astra-human195/DOWNLOADS.json')
manifest = Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
save('PREREG.json', {'method': 'Load actual VoiceEngine using normally installed local wheel, no native module injection. Same47 PCM inputs as203/205/206 through public transcribe_pcm; retain all outputs and compare to greedy203. Run four formerly wrong human segments through actual direct _decode_utterance callback. TTS output object inert, no capture/device/UI/effects. KWS configuration and online recognizer loading stay real; no calibration bypass.',
    'versions': versions, 'native': str(native), 'nativeSha256': sha(native),
    'sourceSha256': sha(root/'src/baxy_mind/voice.py'), 'registrationSha256': sha(manifest),
    'inputs': inputs, 'humans': humans})
class InertOutput:
    speaking = False
    available = False
    def start(self):
        pass
voice.create_speech_output = lambda callback: InertOutput()
published = []
events = []
engine = voice.VoiceEngine(published.append, events.append)
started = time.monotonic()
engine.load()
load_seconds = time.monotonic()-started
audio_inputs = []
for row in inputs:
    path = Path(row['privateOutput'])
    assert sha(path) == row['sha256']
    with np.load(path) as archive:
        for segment in row['segments']:
            audio_inputs.append(archive[f'segment{segment["index"]}'].copy())
for row in humans:
    path = Path(row['asset'])
    assert sha(path) == row['sha256']
    rate, audio = wavfile.read(path)
    assert rate == 16000
    audio_inputs.append(np.r_[np.zeros(16000,np.float32), audio, np.zeros(16000,np.float32)])
audio_inputs.append(np.zeros(32000,np.float32))
assert len(audio_inputs) == len(expected) == 47
results = []
for index, audio in enumerate(audio_inputs):
    started = time.monotonic()
    text = engine.transcribe_pcm(audio)
    result = {'index': index, 'text': text, 'expected': expected[index]['text'],
        'seconds': time.monotonic()-started}
    results.append(result)
    save('RESULTS.json', results)
    assert text == result['expected'], result
engine._mode = 'direct'
direct = []
for case in [3,15,21,23]:
    index = next(i for i, row in enumerate(expected) if row.get('case') == case and row.get('segment') == 0)
    before = len(published)
    engine._decode_utterance(audio_inputs[index], False)
    assert len(published) == before+1
    assert published[-1] == expected[index]['text']
    direct.append({'case': case, 'published': published[-1]})
save('DIRECT.json', direct)
save('COMPLETE.json', {'pcmReadings': len(results), 'identicalTo203': len(results),
    'directRecovered': len(direct), 'engineLoadSeconds': load_seconds,
    'streamingRecognizerLoaded': engine._streaming_recognizer is not None,
    'vadLoaded': engine._vad is not None, 'wakeBackend': engine._wake_backend,
    'wakeError': engine._wake_error, 'rssMiB': psutil.Process().memory_info().rss/2**20,
    'registrationUnchanged': sha(manifest) == read(out/'PREREG.json')['registrationSha256']})
print(json.dumps(read(out/'COMPLETE.json'), ensure_ascii=True), flush=True)
