"""Read-only integration inventory; record no private override values."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/comprobaciones/C03/astra-integration255'
sys.path.insert(0, str(ROOT / 'src'))
from baxy_mind import assets

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical(name):
    return re.sub('[-_.]+', '-', name).lower()

lock = tomllib.loads((ROOT / 'pylock.runtime-win-x64.toml').read_text(encoding='utf-8'))
targets = {'ai-edge-litert', 'backports-strenum', 'ml-dtypes'}
references = []
for package in lock['packages']:
    for raw in metadata.requires(package['name']) or []:
        requirement = Requirement(raw)
        if canonical(requirement.name) in targets:
            references.append({'parent': package['name'], 'requirement': raw,
                               'active': requirement.marker is None or requirement.marker.evaluate()})
descriptor, overrides = assets.load_asset_descriptor(repository_root=ROOT)
override_path, _ = assets._override_path(descriptor, ROOT)
dumpbin = Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/dumpbin.exe')
native = Path('D:/BAXYRuntime/experiments/voice/webrtc255/build/Release/_webrtc_audio.cp312-win_amd64.pyd')
dependencies = subprocess.check_output([str(dumpbin), '/DEPENDENTS', str(native)], text=True)
(OUT / 'NATIVE_DEPENDENCIES.txt').write_text(dependencies, encoding='utf-8')
dependencies = re.findall(r'^\s+([\w.-]+\.dll)\s*$', dependencies, re.MULTILINE | re.IGNORECASE)
assert {d.lower() for d in dependencies} == {'python312.dll', 'winmm.dll', 'kernel32.dll'}
result = {
    'lockedPackages': len(lock['packages']), 'dtlnDependencyParents': references,
    'overridePath': str(override_path), 'overrideExists': override_path is not None and override_path.is_file(),
    'overrideKeys': sorted(overrides), 'hasEchoOverride': 'echo_canceller' in overrides,
    'overrideSha256': sha(override_path) if override_path and override_path.is_file() else None,
    'nativeDependencies': dependencies,
    'productionUnchanged': all(sha(ROOT / name) == value for name, value in json.loads((OUT / 'BEFORE.json').read_text()).items() if name != 'runtime_wheels/README.md'),
}
assert result['productionUnchanged']
(OUT / 'INTEGRATION_INVENTORY.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
print(json.dumps(result))
