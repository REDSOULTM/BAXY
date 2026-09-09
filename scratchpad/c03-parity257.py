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
OUT = BASE / 'astra-parity257'
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

sys.path.insert(0, str(ROOT / 'src'))
from baxy_mind.webrtc_aec import EchoCanceller as Bridge
from baxy_mind.voice import _looks_like_echo

cases = list(read(BASE / 'astra-dsp238/PREREG.json')['cases'])
for number in (243, 254):
    result = read(BASE / f'astra-voice{number}/RESULTS.json')
    source = PRIVATE / f'C03-voice{number}-private/tap{number}.npz'
    entry = next(r for r in result['privateFiles'] if Path(r['path']) == source)
    cases.append({'id': f'echo{number}', 'sourcePath': str(source), 'sourceSha256': entry['sha256'], 'human': None})
linear_rows = {r['case']: r for r in read(BASE / 'astra-linear250/RESULTS.json')}
final_rows = {r['case']: r for r in read(BASE / 'astra-webrtc248/RESULTS.json')}
save('PARITY_PREREG.json', {
    'wheelSha256': sha(WHEEL), 'scriptSha256': sha(Path(__file__)),
    'ownerSha256': sha(ROOT / 'src/baxy_mind/webrtc_aec.py'),
    'captureSha256': sha(ROOT / 'src/baxy_mind/voice.py'),
    'criterion': 'Exact float32 equality, every512sample block, both output views and raw echo guard. 11 frozen253 inputs plus physical254. No tolerance/gain/config change. No ASR rerun needed only if both inputs are exact.',
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
            actual, actual_final, raw, history = engine.process(mic[i], reference[i])
            times.append((time.perf_counter()-start)*1000)
            assert np.array_equal(actual, linear[i]), (case['id'], i, 'linear mismatch', float(np.max(abs(actual-linear[i]))))
            assert np.array_equal(actual_final, final[i]), (case['id'], i, 'final mismatch')
            assert guards[i] == -1 or _looks_like_echo(raw, history) == guards[i], (case['id'], i, 'guard mismatch')
    finally:
        engine.close()
    rows.append({'case': case['id'], 'frames': len(mic), 'linearExact': True, 'finalExact': True, 'guardExact': True,
                 'dspMeanMs': float(np.mean(times)), 'dspP99Ms': float(np.quantile(times, .99))})
    save('PARITY_RESULTS.json', rows)
    print(json.dumps(rows[-1]), flush=True)

signal = np.zeros(25600, np.float32)
signal[8000] = .5
engine = Bridge()
linear, final, raw = [], [], []
for frame in signal.reshape(-1, 512):
    a, suppressed, b, _ = engine.process(frame, np.zeros(4512, np.float32))
    linear.extend(a)
    final.extend(suppressed)
    raw.extend(b)
engine.close()
peaks = [int(np.argmax(abs(np.array(v)))) for v in (linear, final, raw)]
assert peaks == [8256]*3, peaks
save('PARITY_COMPLETE.json', {'cases': len(rows), 'frames': sum(r['frames'] for r in rows), 'impulsePeaks': peaks,
     'allExact': True, 'wheelSha256': sha(WHEEL), 'limitation': 'Installed source257 AEC owner parity; actual capture/ASR/UI/physical validation still needed. C03 stays active with all acceptance requirements.'})
