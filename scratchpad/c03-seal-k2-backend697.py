"""Attest the experimental parser correction and preserve its actual checks."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-k2-parser697-private'
private.mkdir(exist_ok=True, parents=True)
source = Path('D:/BAXYRuntime/build/llama-k2-horizon-35999d1')
binary = source / 'build-cuda13-sm86/bin'
files = ['src/unicode.cpp', 'src/unicode.h', 'src/llama-vocab.cpp', 'common/chat.cpp',
         'common/chat-auto-parser.h', 'common/chat-auto-parser-generator.cpp', 'common/chat-diff-analyzer.cpp',
         'tests/test-chat-auto-parser.cpp']

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

patch = base / 'k2-windows-unicode-parser.patch'
assert not (base / 'BACKEND_BUILD.json').exists(), 'Do not overwrite a sealed backend receipt.'
patch.write_bytes(subprocess.check_output(['git', '-C', str(source), 'diff', '--', *files]))
logs = {}
for name in ['c03-build-k2-tests697.log', 'c03-build-k2-tests697-2.log', 'c03-build-k2-parser697.log',
             'c03-k2-parser697-before.log', 'c03-k2-parser697-before-2.log', 'c03-k2-parser697-after.log',
             'c03-k2-autoparser697-full.log', 'c03-k2-peg697-full.log', 'c03-k2-parser697-full-exits.json']:
    destination = private / name
    shutil.copyfile(Path(os.environ['TEMP']) / name, destination)
    logs[name] = sha(destination)
record = {'utc': datetime.now(timezone.utc).isoformat(), 'source_commit': '35999d101cf2233fc54f09c3c8d599da7303ce02',
    'build_exit': 0, 'build_session': 54702, 'source_modified': True,
    'scope': 'Isolated experimental backend. Existing Windows K2 Unicode/NFC plus effective template kwargs and reasoning-prefix parser correction. BAXY runtime unchanged.',
    'patch': patch.name, 'patch_sha256': sha(patch), 'source_files': {name: sha(source / name) for name in files},
    'backend_files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in binary.iterdir() if p.suffix in ['.dll', '.exe']},
    'private_log_id': private.name, 'log_sha256': logs,
    'targeted_before': {'exit': 1, 'tests': 10, 'assertions': 64, 'failures': 39, 'exceptions': 3, 'skips': 0},
    'targeted_after': {'exit': 0, 'tests': 10, 'assertions': 91, 'failures': 0, 'exceptions': 0, 'skips': 0},
    'full_exits': json.loads((private / 'c03-k2-parser697-full-exits.json').read_text(encoding='utf-8-sig')),
    'non_acceptance_attempts': ['Initial test compile failed because common_json has no ostream formatter in assert_equal; changed assertion to serialized JSON.',
        'Initial test filter matched only the parent (one assertion); corrected regex .* exercised all three efforts and formats.'],
    'note': 'Build adds llama-bench and owner test executables; package hashes, not thin llama-server.exe alone, identify implementation.'}
(base / 'BACKEND_BUILD.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'backend_receipt': str(base / 'BACKEND_BUILD.json'), 'files': len(record['backend_files']), 'full': record['full_exits']}))
