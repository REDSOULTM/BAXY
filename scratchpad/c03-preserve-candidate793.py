"""Preserve measured793 before any further repair; do not adopt it."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'INVENTORY_VETO793'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-inventory-source793-private'
sha = lambda data: hashlib.sha256(data).hexdigest()
pins = json.loads((OUT / 'SOURCE_PINS.json').read_text(encoding='utf-8-sig'))
assert not PRIVATE.exists() and not (OUT / 'SOURCE_SNAPSHOT.json').exists()
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert head == 'ae274b8b4c65a90b3f5707e408a6a63c43b4566a'
patch = []
for relative, digest in pins.items():
    data = (ROOT / relative).read_bytes()
    assert sha(data) == digest and b'\r\n' not in data
    saved = PRIVATE / relative
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_bytes(data)
    prior = subprocess.run(['git', 'show', head + ':' + relative], cwd=ROOT, capture_output=True)
    assert prior.returncode in (0, 128)
    old = prior.stdout if prior.returncode == 0 else b''
    if old != data:
        patch.extend(difflib.unified_diff(old.decode('utf-8').splitlines(keepends=True),
                     data.decode('utf-8').splitlines(keepends=True),
                     fromfile='a/' + relative if prior.returncode == 0 else '/dev/null', tofile='b/' + relative))
patch_path = OUT / 'SOURCE_PATCH.diff'
assert not patch_path.exists()
patch_path.write_bytes(''.join(patch).encode('utf-8'))
subprocess.run(['git', 'apply', '--reverse', '--check', str(patch_path)], cwd=ROOT, check=True)
record = {'utc': datetime.now(timezone.utc).isoformat(), 'candidate_adopted': False,
          'base_commit': head, 'private_directory': str(PRIVATE), 'files': pins,
          'public_patch': 'SOURCE_PATCH.diff', 'patch_sha256': sha(patch_path.read_bytes()),
          'reverse_patch_check_exit': 0, 'reason': '793 repairs three shared false vetoes and preserves source before single-profile integration794. Model choice already closed; no native-model comparison.'}
(OUT / 'SOURCE_SNAPSHOT.json').write_bytes((json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'preserved_files': len(pins), 'patch_bytes': patch_path.stat().st_size, 'adopted': False}))
