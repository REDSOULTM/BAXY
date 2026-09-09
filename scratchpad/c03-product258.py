"""Replay raw fixed inputs through the installed257 capture and actual final ASR."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import queue
import sys
import threading

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import baxy_mind.voice as voice

BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'astra-product258'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-product258-private'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

assert read(BASE / 'astra-parity257/PARITY_COMPLETE.json')['allExact']
assert importlib.metadata.version('pywebrtc-audio') == '0.2.0+baxy.1'
assert importlib.metadata.version('sherpa-onnx') == '1.13.4+baxy.2'
baseline = {r['case']: r for r in read(BASE / 'astra-product253/RESULTS.json')}
inputs = read(BASE / 'astra-linear250/RESULTS.json')
final_inputs = {r['case']: r for r in read(BASE / 'astra-webrtc248/RESULTS.json')}
cases = {r['id']: r for r in read(BASE / 'astra-dsp238/PREREG.json')['cases']}
tap = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-voice243-private/tap243.npz'
record = next(r for r in read(BASE / 'astra-voice243/RESULTS.json')['privateFiles'] if Path(r['path']) == tap)
cases['echo243'] = {'sourcePath': str(tap), 'sourceSha256': record['sha256'], 'human': None}
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)
save(OUT / 'PREREG.json', {
    'scriptSha256': sha(Path(__file__)), 'sourceSha256': sha(ROOT / 'src/baxy_mind/voice.py'),
    'aecSourceSha256': sha(ROOT / 'src/baxy_mind/webrtc_aec.py'),
    'lockSha256': sha(ROOT / 'pylock.runtime-win-x64.toml'),
    'method': 'Unmodified installed257 capture method, native AEC and two real independent VAD states. Finite raw microphone and loopback sources; fixed speaking masks from253. Real baxy.2 final ASR on every new segment. No copied capture method, AEC override, preset guard, output effects or audio device. Compare every segment boundary/PCM/text/cancellation to253.',
    'windows': 'The8fixed windows are unchanged by the DSP parity; reuse their253 transcripts with private-file hash/PCM equality, do not rerun unmodified ASR.',
    'limitation': 'Offline development comparison, not UI, simultaneous human microphone or acoustic acceptance. Existing recognition errors remain.',
    'cases': cases,
})

class Output:
    speaking = False
    available = False
    def start(self):
        pass

class Ducker:
    def duck(self):
        return True
    def restore(self):
        return True

voice.create_speech_output = lambda _: Output()
decoder = voice.VoiceEngine(lambda _: None)
decoder.load()
results = []
for row in inputs:
    case = cases[row['case']]
    raw_path = Path(case['sourcePath'])
    assert sha(raw_path) == case['sourceSha256']
    raw = np.load(raw_path)
    microphone, reference = raw['microphone'], raw['reference']
    if case['human'] is not None:
        original = Path(case['originalPath'])
        assert sha(original) == case['originalSha256']
        rate, human = wavfile.read(original)
        assert rate == 16000
        near = np.zeros(microphone.size, np.float32)
        near[case['onset']:case['onset']+len(human)] = human * case['gain']
        mixed = row['case'].endswith('raw')
        microphone = near.reshape(microphone.shape) + (microphone if mixed else 0)
        if not mixed:
            reference = np.zeros_like(reference)
    assert sha(Path(row['privatePath'])) == row['sha256']
    audio = np.load(row['privatePath'])['clean']
    audio = np.r_[np.zeros(64, np.float32), audio.ravel()][:-64].reshape(audio.shape)
    final_row = final_inputs[row['case']]
    assert sha(Path(final_row['privatePath'])) == final_row['sha256']
    speaking = np.load(final_row['privatePath'])['speaking']
    previous = baseline[row['case']]
    assert sha(Path(previous['privatePath'])) == previous['sha256']
    prior_signals = np.load(previous['privatePath'])
    stop = threading.Event()

    class Stream:
        reads = 0
        device = None
        adc_time = 100.0
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def read(self, count):
            assert count == 512
            if self.reads == len(microphone):
                stop.set()
                return np.zeros((512, 1), np.float32), False
            frame = microphone[self.reads]
            self.reads += 1
            return frame[:, None], False

    stream = Stream()
    class RecordedOutput(Output):
        @property
        def speaking(self):
            return bool(speaking[max(0, stream.reads - 1)])

    voice.create_speech_output = lambda _: RecordedOutput()
    voice.WasapiCaptureStream = lambda *_: stream
    requests, events, cancellations = [], [], []
    engine = voice.VoiceEngine(lambda _: None, events.append)
    engine._mode = 'direct'
    engine._loopback._stream = object()
    engine._loopback.sample_index = lambda *_: 0
    def window_at(end, count, _event):
        assert end == stream.reads * 512 and count == 4512
        return reference[stream.reads - 1]
    engine._loopback.window_at = window_at
    engine._ducker = Ducker()
    engine.probe = lambda: {}
    engine._vad = decoder._vad
    engine._vad.reset()
    engine.cancel_speech = lambda: cancellations.append(stream.reads - 1)
    class Sink:
        def put_nowait(self, request):
            requests.append((stream.reads, request))
    engine._capture_loop(stop_event=stop, decode_queue=Sink(), capture_ready_event=threading.Event())
    assert not any(e.get('event') == 'error' for e in events), events
    assert stream.reads == len(audio)
    segments, signals = [], {}
    for index, (end, request) in enumerate(requests):
        assert request.aec_applied
        first = end * 512 - len(request.audio)
        assert np.array_equal(request.audio, audio.ravel()[first:end * 512])
        signals[f'segment{index}'] = request.audio
        segments.append({'firstSample': first, 'lastSample': end * 512,
            'pcmSha256': hashlib.sha256(request.audio.tobytes()).hexdigest(),
            'text': decoder.transcribe_pcm(request.audio)})
    if row.get('humanWindowSamples') is not None:
        first, last = row['humanWindowSamples']
        assert np.array_equal(audio.ravel()[first:last], prior_signals['humanWindow'])
    target = PRIVATE / f'{row["case"]}-integrated.npz'
    np.savez(target, **signals)
    result = {'case': row['case'], 'segments': segments, 'cancellations': cancellations,
              'humanWindowTextReusedFrom253': previous['humanWindowText'],
              'privatePath': str(target), 'sha256': sha(target),
              'segmentsExactlyMatch253': segments == previous['segments'],
              'cancellationsExactlyMatch253': cancellations == previous['cancellations']}
    results.append(result)
    save(OUT / 'RESULTS.json', results)
    print(json.dumps({k: v for k, v in result.items() if k not in {'privatePath', 'sha256'}}, ensure_ascii=True), flush=True)
    assert result['segmentsExactlyMatch253'] and result['cancellationsExactlyMatch253'], row['case']
save(OUT / 'COMPLETE.json', {'timelines': len(results), 'fixedHumanWindowsReused': 8,
    'segmentsDecoded': sum(len(r['segments']) for r in results), 'allExactlyMatch253': True, 'exitCode': 0})
