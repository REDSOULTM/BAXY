"""Fetch a higher-precision 3.7B control without rewriting earlier weight pins."""
from pathlib import Path
import hashlib
import json
import urllib.request

root = Path(__file__).resolve().parents[1]
folder = Path('D:/BAXYRuntime/experiments/models/k2-horizon-20260909')
repo = 'abenzerps/K2-Horizon-3.7B-GGUF'
revision = '63286c989835381729533e8a16a118a231b0a956'
filename = 'K2-Horizon-3.7B-Q8_0.gguf'
with urllib.request.urlopen(f'https://huggingface.co/api/models/{repo}/tree/{revision}?recursive=false', timeout=60) as response:
    item = next(r for r in json.load(response) if r['path'] == filename)
expected = item['lfs']['oid']
target = folder / filename
url = f'https://huggingface.co/{repo}/resolve/{revision}/{filename}?download=true'

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

if not target.exists():
    partial = target.with_suffix('.gguf.part')
    print(json.dumps({'download': filename, 'bytes': item['size']}), flush=True)
    with urllib.request.urlopen(url, timeout=120) as response, partial.open('wb') as stream:
        while chunk := response.read(4 * 1024 * 1024):
            stream.write(chunk)
    assert partial.stat().st_size == item['size'] and sha(partial) == expected
    partial.rename(target)
assert target.stat().st_size == item['size'] and sha(target) == expected
result = {'repository': repo, 'revision': revision, 'filename': filename, 'bytes': item['size'],
    'sha256': expected, 'path': str(target), 'url': url, 'hash_verified': True,
    'purpose': 'Higher-precision 3.7B control. Q4 alone does not adjudicate full model quality. No promotion.'}
out = root / 'artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696'
(out / (filename + '.json')).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result), flush=True)
