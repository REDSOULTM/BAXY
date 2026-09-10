"""Fetch only named public K2 weights, verify published LFS SHA256, keep isolated."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import urllib.request

root = Path(__file__).resolve().parents[1]
out = Path('D:/BAXYRuntime/experiments/models/k2-horizon-20260909')
out.mkdir(parents=True, exist_ok=True)
evidence = root / 'artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696'
evidence.mkdir(parents=True, exist_ok=True)
specs = [
    ('NANI-Nithin/K2-Horizon-0.9B-GGUF', 'K2-Horizon-0.9B-Q8_0.gguf'),
    ('NANI-Nithin/K2-Horizon-0.9B-GGUF', 'K2-Horizon-0.9B-Q4_K_M.gguf'),
    ('IFM/K2-Horizon-0.9B-GGUF', 'K2-Horizon-1B-BF16.gguf'),
    ('abenzerps/K2-Horizon-3.7B-GGUF', 'K2-Horizon-3.7B-Q4_K_M.gguf'),
]

def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)

def fetch(spec):
    repo, filename = spec
    metadata = get_json(f'https://huggingface.co/api/models/{repo}')
    revision = metadata['sha']
    listing = get_json(f'https://huggingface.co/api/models/{repo}/tree/{revision}?recursive=false')
    item = next(row for row in listing if row['path'] == filename)
    expected = item['lfs']['oid']
    size = item['size']
    url = f'https://huggingface.co/{repo}/resolve/{revision}/{filename}?download=true'
    target = out / filename
    def digest(path):
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    if not target.exists():
        temp = target.with_suffix('.gguf.part')
        print(json.dumps({'downloading': filename, 'bytes': size, 'revision': revision}), flush=True)
        with urllib.request.urlopen(url, timeout=120) as response, temp.open('wb') as stream:
            while chunk := response.read(4 * 1024 * 1024):
                stream.write(chunk)
        assert temp.stat().st_size == size and digest(temp) == expected, filename
        temp.rename(target)
    assert target.stat().st_size == size and digest(target) == expected, filename
    result = {'repository': repo, 'revision': revision, 'filename': filename, 'bytes': size,
              'sha256': expected, 'path': str(target), 'url': url, 'hash_verified': True}
    (evidence / (filename + '.json')).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'verified': filename, 'sha256': expected}), flush=True)
    return result

with ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(fetch, specs))
(evidence / 'WEIGHTS.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
