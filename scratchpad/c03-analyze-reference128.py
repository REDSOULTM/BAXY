"""Inspect exact runtime127 pairs against existing full loopback; no effects."""
from pathlib import Path
import hashlib
import json
import os
import wave
import numpy as np
from scipy.signal import resample_poly

root = Path(__file__).resolve().parents[1]
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-voice127-private'
out = root / 'artifacts/comprobaciones/C03/astra-voice127'
metadata = json.loads((private / 'runtime-observations.json').read_text(encoding='utf-8'))
data = np.load(private / 'runtime-observations.npz')
with wave.open(str(private / 'loopback.wav'), 'rb') as wav:
    rate = wav.getframerate()
    full = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').reshape(-1, wav.getnchannels()).mean(axis=1)
full = resample_poly(full, 16000, rate)

def score(mic, ref):
    mic = mic.astype(np.float64)
    ref = ref.astype(np.float64)
    mic -= mic.mean()
    products = np.correlate(ref, mic, mode='valid')
    sums = np.concatenate(([0.], np.cumsum(ref)))
    squares = np.concatenate(([0.], np.cumsum(ref * ref)))
    totals = sums[mic.size:] - sums[:-mic.size]
    energy = squares[mic.size:] - squares[:-mic.size] - totals * totals / mic.size
    norms = np.linalg.norm(mic) * np.sqrt(np.maximum(energy, 0.))
    scores = np.divide(abs(products), norms, out=np.zeros_like(products), where=norms > 1e-6)
    best = int(np.argmax(scores))
    return {'score': float(scores[best]), 'referenceStartSample': best}

rows = []
floor = .002
floors = []
for frame in metadata['vad']:
    if frame['probability'] < .5:
        floor = .98 * floor + .02 * frame['rms']
    floors.append(floor)
for i, echo in enumerate(metadata['echo']):
    vad = metadata['vad'][echo['vadIndex']]
    if vad['rms'] < max(.004, floors[echo['vadIndex']] * 1.8):
        continue
    mic, reference = data['echo_microphone'][i], data['echo_reference'][i]
    row = {**echo, 'rms': vad['rms'], 'runtimeReference': score(mic, reference),
           'wholeRecording': score(mic, full)}
    rows.append(row)
report = {'vadFrames': len(metadata['vad']), 'echoCalls': len(metadata['echo']),
          'echoTrue': sum(e['echo'] for e in metadata['echo']),
          'qualifiedFrames': len(rows), 'qualifiedFalse': sum(not e['echo'] for e in rows),
          'limit': 'Upper bound comparison over full external capture; same-waveform fit can distinguish missing reference from low waveform similarity, not validate an acoustic classifier.',
          'rows': rows}
target = private / 'reference128.json'
with target.open('x', encoding='utf-8') as f:
    json.dump(report, f, indent=2)
with (out / 'OBSERVATION_INDEX.json').open('x', encoding='utf-8') as f:
    json.dump({'files': [{'privatePath': str(private / name), 'sha256': hashlib.sha256((private / name).read_bytes()).hexdigest()} for name in ['runtime-observations.json', 'runtime-observations.npz', 'reference128.json']]}, f, indent=2)
print(json.dumps({k: v for k, v in report.items() if k != 'rows'}))
print(json.dumps([{'frame': r['vadIndex'], 'echo': r['echo'], 'rms': round(r['rms'], 5),
                  'runtimeScore': round(r['runtimeReference']['score'], 3),
                  'fullScore': round(r['wholeRecording']['score'], 3)} for r in rows]))
