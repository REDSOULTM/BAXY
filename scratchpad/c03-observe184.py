"""Adjudicate preserved physical183 audio locally; no expected-text hints."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import time
import wave

import numpy as np
import psutil
from scipy.signal import resample_poly
import sherpa_onnx

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
source = base / 'astra-sidecar183'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-sidecar183-private'
out = base / 'astra-observe184'
out.mkdir(exist_ok=False)
assert not any(p.info['name'] in {'Baxy.exe', 'llama-server.exe', 'piper.exe'}
               for p in psutil.process_iter(['name']))
capture = json.loads((source / 'AUDIO_RESULT.json').read_text(encoding='utf-8'))
assert capture['threadsStopped'] and capture['restoredExactly']
assert all(s['overflows'] == 0 for s in capture['streams'].values())
events = [json.loads(line) for line in (private / 'tts-state.jsonl').read_text(encoding='utf-8').splitlines()]
intervals = []
for i, event in enumerate(events):
    if event['speaking']:
        end = next(e for e in events[i+1:] if not e['speaking'])
        intervals.append((event['time'], end['time']))
assert len(intervals) == 4
clock_samples = []
for _ in range(8):
    before = time.monotonic()
    wall = time.time()
    after = time.monotonic()
    clock_samples.append({'monotonicBefore': before, 'wall': wall, 'monotonicAfter': after,
                          'offset': wall-(before+after)/2})
offset = float(np.median([r['offset'] for r in clock_samples]))
manifest_path = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
inputs = []
signals = {}
for name, record in capture['streams'].items():
    path = Path(record['privatePath'])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == record['sha256']
    with wave.open(str(path), 'rb') as wav:
        assert wav.getsampwidth() == 2
        rate, channels = wav.getframerate(), wav.getnchannels()
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), '<i2').astype(np.float32)
    signal = pcm.reshape(-1, channels).mean(axis=1)/32768
    if rate != 16000:
        assert rate == 48000
        signal = resample_poly(signal, 1, 3).astype(np.float32)
    signals[name] = signal
    inputs.append({'name': name, 'path': str(path), 'sha256': digest, 'rate': rate,
                   'channels': channels, 'resampledSamples': len(signal)})
windows = []
for index, (start, end) in enumerate(intervals):
    for name, record in capture['streams'].items():
        origin = dt.datetime.fromisoformat(record['streamReadyUtc']).timestamp()
        first = max(0, round((start+offset-origin-1)*16000))
        last = min(len(signals[name]), round((end+offset-origin+1)*16000))
        assert last > first
        windows.append({'output': index+1, 'channel': name, 'samples': [first, last],
                        'speakingSeconds': end-start})
prereg = {'method': 'Preserved physical183; registered Parakeet CPU6 beam8, no hints. All four intervals, microphone and loopback, raw and peak0.8 normalization. Mono mean then scipy resample_poly48000->16000 for loopback.',
          'limitation': '183 speaking state has monotonic only; map with wall-minus-monotonic measured now on same boot. Assumes no intervening wall clock jump. Use one second margin each side and preserve boundaries/energy. Recognition and normalization are diagnostic, not proof of human input or complete fidelity.',
          'clockSamples': clock_samples, 'offsetSeconds': offset, 'inputs': inputs,
          'windows': windows, 'runtimeManifestSha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
stt = Path(manifest['stt_dir'])
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(stt/'encoder.int8.onnx'), decoder=str(stt/'decoder.int8.onnx'),
    joiner=str(stt/'joiner.int8.onnx'), tokens=str(stt/'tokens.txt'), num_threads=6,
    model_type='nemo_transducer', decoding_method='modified_beam_search', max_active_paths=8)
rows = []
for window in windows:
    first, last = window['samples']
    raw = signals[window['channel']][first:last]
    peak = float(np.max(np.abs(raw)))
    rms = float(np.sqrt(np.mean(raw*raw)))
    blocks = raw[:len(raw)//320*320].reshape(-1, 320)
    activity = np.flatnonzero(np.sqrt(np.mean(blocks*blocks, axis=1)) >= 0.001)
    activity_range = [int(activity[0])*0.02, (int(activity[-1])+1)*0.02] if len(activity) else None
    for normalized in [False, True]:
        signal = raw*(0.8/peak) if normalized and peak else raw
        stream = recognizer.create_stream()
        stream.accept_waveform(16000, signal)
        started = time.monotonic()
        recognizer.decode_stream(stream)
        row = {**window, 'normalized': normalized, 'peak': peak, 'rms': rms,
               'activityRms001SecondsInWindow': activity_range,
               'text': str(stream.result.text or '').strip(), 'decodeSeconds': time.monotonic()-started}
        rows.append(row)
        (out/'RESULTS.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(row, ensure_ascii=False), flush=True)
(out/'COMPLETE.json').write_text(json.dumps({'readings': len(rows), 'exit': 'complete'}), encoding='utf-8')
