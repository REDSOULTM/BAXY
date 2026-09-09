"""Verify exact campaign pins before publication; no artifact rewriting."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
names = [
    'observe-identity593', 'guard-boundary594', 'guard-contract595',
    'language-repair596', 'language-wire597', 'language-backend598',
    'language-template599', 'history-request600', 'language-translation601',
    'language-repair602', 'conversation-regression603',
    'language-sentences604', 'conversation-regression605',
]
if '--include-full' in sys.argv:
    names.append('language-literals606')
count = 0
for name in names:
    folder = base / ('astra-' + name)
    pins = json.loads((folder / 'PINS.json').read_text(encoding='utf-8'))
    for relative, expected in pins.items():
        path = folder / relative
        assert path.resolve().is_relative_to(folder.resolve()), path
        content = path.read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected, path
        if '--staged' in sys.argv:
            staged = subprocess.check_output(
                ['git', 'show', ':' + path.relative_to(root).as_posix()], cwd=root,
            )
            assert hashlib.sha256(staged).hexdigest() == expected, ('staged', path)
        count += 1
print(json.dumps({'campaigns': len(names), 'pins_verified': count,
                  'staged': '--staged' in sys.argv}))
