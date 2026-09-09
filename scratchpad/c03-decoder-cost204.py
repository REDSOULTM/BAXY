"""Measure two native decoding contexts before changing the product."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

import numpy as np
import psutil
import sherpa_onnx

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind.voice import _compile_contextual_hotwords, _decode_offline_text
from baxy_mind.voice import WakePhraseMatcher

out = root / 'artifacts/comprobaciones/C03/astra-decoder-cost204'
out.mkdir(exist_ok=False)
manifest_path = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
stt = Path(manifest['stt_dir'])
process = psutil.Process()

def save(name, data):
    (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

save('PREREG.json', {
    'method': 'Measure CPU RSS and construction/warmup time for greedy primary and unchanged beam8 contextual recognizer in one process. Same registered int8 Parakeet, CPU6 each. No product/runtime mutation or hardware playback. One original human segment and silence on each; beam receives current wake aliases compiled by product.',
    'runtimeSha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    'version': sherpa_onnx.__version__,
})
segments = json.loads((root / 'artifacts/comprobaciones/C03/astra-segment201-retry/RESULTS.json').read_text(encoding='utf-8'))
row = next(r for r in segments if r['case'] == 23)
path = Path(row['privateOutput'])
assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
with np.load(path) as archive:
    speech = archive['segment0'].copy()
hotwords = _compile_contextual_hotwords(stt / 'tokens.txt', WakePhraseMatcher().aliases)
results = {'baselineRssMiB': process.memory_info().rss / 2**20, 'contexts': []}
recognizers = []
for method in ['greedy_search', 'modified_beam_search']:
    before = process.memory_info().rss
    start = time.monotonic()
    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(stt/'encoder.int8.onnx'), decoder=str(stt/'decoder.int8.onnx'),
        joiner=str(stt/'joiner.int8.onnx'), tokens=str(stt/'tokens.txt'),
        num_threads=6, model_type='nemo_transducer', decoding_method=method,
        max_active_paths=8, hotwords_score=5,
    )
    built = time.monotonic()
    silence = _decode_offline_text(recognizer, np.zeros(8000, np.float32),
        hotwords=hotwords if method == 'modified_beam_search' else '')
    warmed = time.monotonic()
    text = _decode_offline_text(recognizer, speech,
        hotwords=hotwords if method == 'modified_beam_search' else '')
    results['contexts'].append({'method': method, 'buildSeconds': built-start,
        'warmupSeconds': warmed-built, 'decodeSeconds': time.monotonic()-warmed,
        'rssMiB': process.memory_info().rss/2**20,
        'incrementRssMiB': (process.memory_info().rss-before)/2**20,
        'silenceText': silence, 'speechText': text})
    recognizers.append(recognizer)
    save('RESULTS.json', results)
save('COMPLETE.json', {'contexts': len(recognizers), 'sourceChanged': False})
print(json.dumps(results, ensure_ascii=True), flush=True)
