"""Check physical capture evidence and report bounded signal metrics."""
import hashlib
import json
import os
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'astra-voice259'
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
result = read(OUT / 'RESULTS.json')
for row in result['privateFiles']:
    assert sha(Path(row['path'])) == row['sha256']
for path, expected in read(OUT / 'PREREG.json')['sourceFiles'].items():
    assert sha(ROOT / path) == expected
assert result['generated'] == 4 and result['bargeInCount'] == result['transcriptCount'] == 0
assert result['restoredExactly'] and not result['voiceErrors'] and not result['driverErrors']
assert not any(result['workersAlive'].values()) and not result['outputWorkerAlive']
path = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-voice259-private/tap259.npz'
data = np.load(path)
obs = data['observations']
speaking = obs[:, 3].astype(bool)
assert np.isfinite(obs).all() and speaking.any()
metrics = {'frames': len(obs), 'speakingFrames': int(speaking.sum()), 'audioSeconds': len(obs)*.032,
    'dspMeanMs': float(obs[:,1].mean()), 'dspP99Ms': float(np.quantile(obs[:,1], .99)),
    'dspMaxMs': float(obs[:,1].max()), 'linearVadMax': float(obs[:,4].max()),
    'confirmationVadMax': float(obs[:,6].max()),
    'note': 'DSP timing excludes VAD/UI/LLM. Speaking signal proves nonzero input/reference, not simultaneous human speech or full C03 resource acceptance.'}
for key in ('microphone', 'reference', 'clean', 'confirmation'):
    values = data[key][speaking].astype(np.float64)
    metrics[key+'RmsDuringOutput'] = float(np.sqrt(np.mean(values**2)))
assert metrics['microphoneRmsDuringOutput'] > 0 and metrics['referenceRmsDuringOutput'] > 0
(OUT / 'TRACE_METRICS.json').write_text(json.dumps(metrics, indent=2)+'\n', encoding='utf-8')
print(json.dumps(metrics))
