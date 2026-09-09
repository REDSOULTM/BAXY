"""Fetch one pinned English Piper voice for an isolated local experiment."""
from pathlib import Path
import datetime
import hashlib
import json
import urllib.request

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-native-tts114'
out.mkdir(exist_ok=False)
target = Path('D:/BAXYRuntime/experiments/voice/c03-john114')
target.mkdir(parents=True, exist_ok=False)
base = 'https://huggingface.co/rhasspy/piper-voices/resolve/'
folder = 'en/en_US/john/medium'
with urllib.request.urlopen(f'{base}main/{folder}/MODEL_CARD', timeout=30) as response:
    revision = response.headers['x-repo-commit']
    card = response.read().decode('utf-8')
assert revision and len(revision) == 40
assert 'public domain' in card and 'en_US' in card
with urllib.request.urlopen(f'https://huggingface.co/api/models/rhasspy/piper-voices/tree/{revision}/{folder}', timeout=30) as response:
    metadata = json.load(response)
files = []
for name in ('MODEL_CARD', 'en_US-john-medium.onnx.json', 'en_US-john-medium.onnx'):
    entry = next(x for x in metadata if x['path'] == f'{folder}/{name}')
    url = f'{base}{revision}/{folder}/{name}'
    path = target / name
    with urllib.request.urlopen(url, timeout=60) as response, path.open('xb') as dest:
        while chunk := response.read(1024 * 1024):
            dest.write(chunk)
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    assert path.stat().st_size == entry['size']
    if entry.get('lfs'):
        assert digest == entry['lfs']['oid']
    files.append({'path': str(path), 'url': url, 'bytes': path.stat().st_size,
                  'sha256': digest, 'upstream': entry})
report = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'revision': revision, 'modelCard': card, 'files': files,
          'method': 'Only public assets downloaded; no user data uploaded. English male medium Piper '
                    'voice, dataset listed as public domain. Existing configured voice locations '
                    'contain Spanish baxy-es only; home .gemma4 configured candidates absent. '
                    'Experiment only, no registered runtime mutation or promotion.',
          'heritage': 'biblioteca/carter/legacy/Carter_v2/MODEL_TTS_TOURNAMENT_REPORT.md:69-73; '
                      '2026-05-02, per-language voices; scaffold latency is not measured acceptance.',
          'hypothesis': 'Source112 correct PAD and English eSpeak still fail two contents with Spanish '
                        'voice (native113). Test English-trained john medium using same engine and '
                        'three consumed texts; no classifier or new backend.'}
(out / 'DOWNLOAD.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'revision': revision, 'files': [{k: x[k] for k in ('path', 'bytes', 'sha256')} for x in files]}))
