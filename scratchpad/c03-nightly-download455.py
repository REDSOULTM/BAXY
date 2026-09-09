"""Download official b10865 for the applicable post-stable fixes audited454."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
import zipfile

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-nightly-download455'
out.mkdir(exist_ok=False)
target = Path('D:/BAXYRuntime/assets/llama-b10865-cuda12.4')
downloads = Path('D:/BAXYRuntime/assets/downloads/C03-backend455')
assert not target.exists() and not downloads.exists()
assert shutil.disk_usage(target.parent).free > 2 * 2**30
downloads.mkdir()
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

def request(url):
    return urllib.request.Request(url, headers={'User-Agent': 'BAXY-C03-local-audit'})

initial = sha(manifest)
url = 'https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b10865'
with urllib.request.urlopen(request(url), timeout=30) as response:
    release = json.load(response)
write(out / 'RELEASE.json', release)
names = ['llama-b10865-bin-win-cuda-12.4-x64.zip', 'cudart-llama-bin-win-cuda-12.4-x64.zip']
assets = [next(a for a in release['assets'] if a['name'] == name) for name in names]
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'purpose': '454 identified post-stable GDN normalization correction28068 for qwen35, CUDA fixes and checkpoint eviction28302. Download the exact observed official nightly b10865 side by side. Do not promote runtime. Concurrent453 inference durations are diagnostic, not clean benchmarks, because audit/download may overlap.',
    'target': str(target), 'assets': [{k: a[k] for k in ['name', 'size', 'digest', 'browser_download_url']} for a in assets],
    'manifest_sha256': initial,
})
verified = []
for asset in assets:
    assert asset['digest'].startswith('sha256:')
    expected = asset['digest'].split(':', 1)[1]
    cached = Path('D:/BAXYRuntime/assets/downloads/C03-backend448') / asset['name']
    if cached.is_file() and cached.stat().st_size == asset['size'] and sha(cached) == expected:
        archive = cached
        reused = True
    else:
        archive = downloads / asset['name']
        partial = archive.with_suffix(archive.suffix + '.partial')
        with urllib.request.urlopen(request(asset['browser_download_url']), timeout=60) as response, partial.open('xb') as output:
            shutil.copyfileobj(response, output, length=2**20)
        assert partial.stat().st_size == asset['size'] and sha(partial) == expected
        partial.rename(archive)
        reused = False
    verified.append({'path': str(archive), 'sha256': expected, 'bytes': asset['size'], 'reused': reused})
    print(json.dumps(verified[-1]), flush=True)
target.mkdir()
for item in verified:
    with zipfile.ZipFile(item['path']) as archive:
        for member in archive.infolist():
            resolved = (target / member.filename).resolve()
            assert resolved.is_relative_to(target.resolve()), member.filename
        archive.extractall(target)
server = target / 'llama-server.exe'
assert server.is_file()
version = subprocess.run([str(server), '--version'], capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
assert version.returncode == 0
write(out / 'RESULT.json', {
    'release': {k: release[k] for k in ['tag_name', 'published_at', 'prerelease', 'target_commitish', 'html_url']},
    'archives': verified, 'server': str(server), 'version': (version.stdout + version.stderr).strip(),
    'server_sha256': sha(server), 'files': {p.name: sha(p) for p in target.iterdir() if p.is_file()},
    'manifest_unchanged': sha(manifest) == initial, 'promoted': False,
})
assert sha(manifest) == initial
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
print(json.dumps({'server': str(server), 'sha256': sha(server), 'version': (version.stdout + version.stderr).strip(), 'manifest_unchanged': True}), flush=True)
