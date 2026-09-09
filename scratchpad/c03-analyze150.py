"""Inspect the exact arrays consumed in149; no playback, VAD or source mutation."""
from pathlib import Path
import hashlib
import json
import os

import numpy as np
from scipy.signal import correlate, correlation_lags

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-analysis150'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-voice149-private'
index = json.loads((root / 'artifacts/comprobaciones/C03/astra-voice149/OBSERVATION_INDEX.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256(Path(row['privatePath']).read_bytes()).hexdigest() == row['sha256'] for row in index)
data = np.load(private / 'tap149.npz')
metadata = json.loads((private / 'tap149.json').read_text(encoding='utf-8'))
mic = data['microphone'].astype(np.float64).ravel()
ref = data['reference'][:, -512:].astype(np.float64).ravel() / 32768
clean = data['clean'].astype(np.float64).ravel()
correlation = correlate(mic, ref, mode='full', method='fft')
lags = correlation_lags(mic.size, ref.size, mode='full')
allowed = np.flatnonzero(np.abs(lags) <= 8000)
best = allowed[np.argmax(np.abs(correlation[allowed]))]
lag = int(lags[best])
result = {'source': 149, 'frames': len(metadata['frames']), 'anchor': metadata['anchor'],
          'micMinusReferenceLagSamples': lag, 'lagMilliseconds': lag / 16,
          'correlation': float(abs(correlation[best]) / (np.linalg.norm(mic) * np.linalg.norm(ref) + 1e-20)),
          'historyContinuous': bool(np.array_equal(data['reference'][1:, :-512], data['reference'][:-1, 512:])),
          'vadFrames': []}
for i, frame in enumerate(metadata['frames']):
    raw_rms = float(np.sqrt(np.mean(data['microphone'][i] ** 2)))
    clean_rms = float(np.sqrt(np.mean(data['clean'][i] ** 2)))
    if frame.get('probability', 0) >= .5:
        result['vadFrames'].append({'index': i, **frame, 'rawRms': raw_rms, 'cleanRms': clean_rms,
                                   'referenceRms': float(np.sqrt(np.mean((data['reference'][i, -512:].astype(np.float64) / 32768) ** 2)))})
(out / 'RESULTS.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
