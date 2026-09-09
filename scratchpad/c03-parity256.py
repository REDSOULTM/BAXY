"""Attest the new native package against all fixed two-view development inputs."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import zipfile

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'astra-parity256'
OUT.mkdir(exist_ok=False)
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
WORK = Path('D:/BAXYRuntime/experiments/voice/webrtc255')
WHEEL = ROOT / 'runtime_wheels/pywebrtc_audio-0.2.0+baxy.1-cp312-cp312-win_amd64.whl'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')

installed = WORK / 'python'
with zipfile.ZipFile(WHEEL) as archive:
    for name in archive.namelist():
        assert (installed / name).read_bytes() == archive.read(name)
sys.path.insert(0, str(installed))
sys.path.insert(0, str(ROOT / 'src'))
from pywebrtc_audio import EchoCanceller as Native
from baxy_mind.voice import _looks_like_echo
assert not hasattr(Native(), 'diagnostic_metrics')
# The bridge is the frozen254 implementation, with only its native import changed.
adapter_source = (ROOT / 'scratchpad/webrtc_aligned254.py').read_text(encoding='utf-8')
class_source = adapter_source[adapter_source.index('class EchoCanceller:'):]
namespace = dict(Native=Native, np=np, WHEEL_SHA=sha(WHEEL))
import threading
namespace['threading'] = threading
exec(compile(class_source, 'frozen254-bridge-with-native255', 'exec'), namespace)
Bridge = namespace['EchoCanceller']

cases = []
for number in (254,):
    result = read(BASE / f'astra-voice{number}/RESULTS.json')
    source = PRIVATE / f'C03-voice{number}-private/tap{number}.npz'
    entry = next(r for r in result['privateFiles'] if Path(r['path']) == source)
    cases.append({'id': f'echo{number}', 'sourcePath': str(source), 'sourceSha256': entry['sha256'], 'human': None})
linear_rows = {r['case']: r for r in read(BASE / 'astra-linear250/RESULTS.json')}
final_rows = {r['case']: r for r in read(BASE / 'astra-webrtc248/RESULTS.json')}
save('PARITY_PREREG.json', {
    'wheelSha256': sha(WHEEL), 'scriptSha256': sha(Path(__file__)),
    'adapterSha256': sha(ROOT / 'scratchpad/webrtc_aligned254.py'),
    'criterion': 'Only remaining physical254: both signals exact in every512sample block; guard compared only where recorded0/1. Sentinel -1 means uncalled, never True. Previous255 eleven full inputs remain exact. Same package/bridge/input; no tolerance or algorithm change.',
    'cases': cases,
})
rows = []
for case in cases:
    path = Path(case['sourcePath'])
    assert sha(path) == case['sourceSha256']
    data = np.load(path)
    mic, reference = data['microphone'], data['reference']
    if case['human'] is not None:
        original = Path(case['originalPath'])
        assert sha(original) == case['originalSha256']
        rate, audio = wavfile.read(original)
        assert rate == 16000
        near = np.zeros(mic.size, np.float32)
        near[case['onset']:case['onset']+len(audio)] = audio * case['gain']
        mixed = case['id'].endswith('raw')
        mic = near.reshape(mic.shape) + (mic if mixed else 0)
        if not mixed:
            reference = np.zeros_like(reference)
    if case['id'] == 'echo254':
        linear, final = data['clean'], data['confirmation']
        guards = data['observations'][:, 5]
        assert set(guards) <= {-1, 0, 1}
    else:
        linear_row, final_row = linear_rows[case['id']], final_rows[case['id']]
        assert sha(Path(linear_row['privatePath'])) == linear_row['sha256']
        assert sha(Path(final_row['privatePath'])) == final_row['sha256']
        linear = np.load(linear_row['privatePath'])['clean']
        linear = np.r_[np.zeros(64, np.float32), linear.ravel()][:-64].reshape(linear.shape)
        final_data = np.load(final_row['privatePath'])
        final, guards = final_data['clean'], final_data['guards']
    engine = Bridge()
    times = []
    try:
        for i in range(len(mic)):
            start = time.perf_counter()
            actual, raw, history = engine.process(mic[i], reference[i])
            times.append((time.perf_counter()-start)*1000)
            assert np.array_equal(actual, linear[i]), (case['id'], i, 'linear mismatch', float(np.max(abs(actual-linear[i]))))
            assert np.array_equal(engine.last_final, final[i]), (case['id'], i, 'final mismatch')
            assert guards[i] == -1 or _looks_like_echo(raw, history) == guards[i], (case['id'], i, 'guard mismatch')
    finally:
        engine.close()
    rows.append({'case': case['id'], 'frames': len(mic), 'linearExact': True, 'finalExact': True, 'guardExact': True, 'observedGuardsCompared': int(np.sum(guards >= 0)),
                 'dspMeanMs': float(np.mean(times)), 'dspP99Ms': float(np.quantile(times, .99))})
    save('PARITY_RESULTS.json', rows)
    print(json.dumps(rows[-1]), flush=True)

signal = np.zeros(25600, np.float32)
signal[8000] = .5
engine = Bridge()
linear, final, raw = [], [], []
for frame in signal.reshape(-1, 512):
    a, b, _ = engine.process(frame, np.zeros(4512, np.float32))
    linear.extend(a)
    final.extend(engine.last_final)
    raw.extend(b)
engine.close()
peaks = [int(np.argmax(abs(np.array(v)))) for v in (linear, final, raw)]
assert peaks == [8256]*3, peaks
save('PARITY_COMPLETE.json', {'cases': len(rows), 'frames': sum(r['frames'] for r in rows), 'impulsePeaks': peaks,
     'allExact': True, 'wheelSha256': sha(WHEEL), 'limitation': 'Native package parity only; production capture/lock/runtime not yet replaced. C03 stays active with all acceptance requirements.'})
