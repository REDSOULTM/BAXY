"""Seal the official K2 tool-boundary correction and its regression checks."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-k2-parser698-private'
private.mkdir(parents=True, exist_ok=False)
source = Path('D:/BAXYRuntime/build/llama-k2-horizon-35999d1')
binary = source / 'build-cuda13-sm86/bin'
previous = json.loads((base / 'BACKEND_BUILD.json').read_text(encoding='utf-8'))

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

receipt = base / 'BACKEND_BUILD698.json'
assert not receipt.exists()
patch = base / 'k2-windows-unicode-parser698.patch'
patch.write_bytes(subprocess.check_output(['git', '-C', str(source), 'diff', '--', *previous['source_files']]))
logs = {}
for name in ['c03-k2-parser698-test-build.log', 'c03-k2-parser698-test-build2.log',
             'c03-k2-parser698-before.log', 'c03-k2-parser698-build.log', 'c03-k2-parser698-after.log',
             'c03-k2-autoparser698-full.log', 'c03-k2-peg698-full.log', 'c03-k2-parser698-full-exits.json']:
    shutil.copyfile(Path(os.environ['TEMP']) / name, private / name)
    logs[name] = sha(private / name)
full = json.loads((private / 'c03-k2-parser698-full-exits.json').read_text(encoding='utf-8-sig'))
assert full == {'autoparser': 0, 'peg': 0}
record = {'utc': datetime.now(timezone.utc).isoformat(), 'source_commit': previous['source_commit'],
    'build_exit': 0, 'build_session': 74918, 'source_modified': True,
    'scope': 'Experimental backend only. Retains697 fixes; K2 tool opening ends reasoning implicitly as in official SGLang. Mismatched effort delimiters do not become visible prose. No BAXY runtime promotion.',
    'source': 'https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/parser/reasoning_parser.py#L440-L491',
    'patch': patch.name, 'patch_sha256': sha(patch),
    'source_files': {name: sha(source / name) for name in previous['source_files']},
    'backend_files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in binary.iterdir() if p.suffix in ['.exe', '.dll']},
    'private_log_id': private.name, 'log_sha256': logs,
    'before': {'exit': 1, 'tests': 10, 'assertions': 3943, 'failures': 36, 'exceptions': 0, 'skips': 0},
    'targeted_after': {'exit': 0, 'tests': 10, 'assertions': 4015, 'failures': 0, 'exceptions': 0, 'skips': 0},
    'full_autoparser': {'exit': 0, 'tests': 121, 'assertions': 4539, 'failures': 0, 'exceptions': 0, 'skips': 0},
    'full_peg': {'exit': 0, 'tests': 39, 'assertions': 210, 'failures': 0, 'exceptions': 0, 'skips': 0},
    'method': 'All three request-selected efforts, prose/XML/JSON, matching and mismatched emitted closes, repeated high opening, implicit tool boundary and every streaming prefix through each close. Strict prose behavior follows the official parser.'}
receipt.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'receipt': str(receipt), 'backend_files': len(record['backend_files'])}))
