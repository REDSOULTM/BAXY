"""Record and install the declared ASR runtime dependency with pip hash checking."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03/astra-install207'
out.mkdir(exist_ok=False)
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def save(name, value):
    (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
manifest = Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
sources = ['src/baxy_mind/voice.py','src/baxy_mind/requirements-voice.txt',
    'scripts/build_sherpa_runtime.py','scripts/verify_python_runtime_lock.py',
    'scripts/lock_python_dependencies.ps1','constraints-runtime-win-x64.txt',
    'pylock.runtime-win-x64.toml','tests/test_mind_voice_runtime.py',
    'tests/test_python_runtime_lock.py','tests/test_sherpa_runtime_package.py',
    'runtime_wheels/sherpa-nemo-stream-decoder.patch',
    'runtime_wheels/sherpa_onnx-1.13.4+baxy.1-cp312-cp312-win_amd64.whl']
before = {dist.metadata['Name']: dist.version for dist in importlib.metadata.distributions()}
save('PREREG.json', {'createdAtUtc': datetime.now(timezone.utc).isoformat(),
    'before': before, 'registrationSha256': sha(manifest),
    'sources': {name: sha(root/name) for name in sources},
    'method': 'Install complete declared runtime lock with only-binary, require-hashes, no-deps. Expected version change only sherpa-onnx1.13.4 to1.13.4+baxy.1. Keep core1.13.4 and all model/registration assets. Native extension already validated206; Python owner91 and wheel identity/integrity1 passed. Product-native audio follows after installation.',
    'rollbackWheel': 'D:/BAXYRuntime/experiments/voice/sherpa205/sherpa_onnx-1.13.4-cp312-cp312-win_amd64.whl'})
command = [sys.executable,'-m','pip','install','--disable-pip-version-check',
    '--only-binary=:all:','--require-hashes','--no-deps','--report',str(out/'PIP_REPORT.json'),
    '-r',str(root/'pylock.runtime-win-x64.toml')]
result = subprocess.run(command, cwd=root, check=False)
save('COMPLETE.json', {'exitCode': result.returncode, 'registrationUnchanged': sha(manifest) == json.loads((out/'PREREG.json').read_text(encoding='utf-8'))['registrationSha256']})
raise SystemExit(result.returncode)
