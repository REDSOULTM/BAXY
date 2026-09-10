"""Pin the isolated Windows backend and record compatibility diagnostics."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696'
source = Path('D:/BAXYRuntime/build/llama-k2-horizon-35999d1')
binary = source / 'build-cuda13-sm86/bin'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-k2-backend696-private'
private.mkdir(exist_ok=True, parents=True)

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

patch = subprocess.check_output(['git', '-C', str(source), 'diff', '--', 'src/unicode.cpp', 'src/unicode.h', 'src/llama-vocab.cpp'])
patch_path = base / 'k2-unicode-nfc-windows.patch'
patch_path.write_bytes(patch)
log = private / 'BUILD_NFC.log'
shutil.copyfile(Path(os.environ['TEMP']) / 'c03-build-k2-nfc696.log', log)
write(base / 'BACKEND_BUILD_NFC.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'session': 14005, 'exit': 0,
    'source_commit': subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
    'source_modified': True, 'scope': 'Private Windows-only backend. K2 regex custom split and official NFC normalization. No model weights or BAXY production source changed.',
    'patch': str(patch_path.relative_to(root)), 'patch_sha256': sha(patch_path),
    'source_files': {str(p): sha(source / p) for p in ['src/unicode.cpp', 'src/unicode.h', 'src/llama-vocab.cpp']},
    'cuda': '13.0.88', 'architecture': '86', 'config': 'Release', 'build_parallelism': 3,
    'raw_log': str(log), 'raw_log_sha256': sha(log),
    'files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(binary.iterdir()) if p.suffix in ['.dll', '.exe']},
    'previous_diagnostics': [
        {'tag': 'q8-auto', 'result': 'Original backend fails regex_error(error_escape) before readiness. No generation.'},
        {'tag': 'q8-unicode1', 'result': 'Custom regex backend loads; 261/285 official token ID parity, 24 mismatches fully explained by missing NFC (285/285 when reference NFC disabled). No generation. Intermediate DLL hashes not captured; initial patch and output retained.'},
    ],
})
print('Patched backend build pinned')
