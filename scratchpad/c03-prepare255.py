"""Preserve integration inputs and derive the minimal native export patch."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/comprobaciones/C03/astra-integration255'
OUT.mkdir(exist_ok=False)
paths = [
    'src/baxy_mind/dtln_aec.py', 'src/baxy_mind/voice.py',
    'src/baxy_mind/voice_capture.py', 'src/baxy_mind/requirements-voice.txt',
    'src/baxy_mind/licenses/DTLN-aec.txt', 'scripts/install_dtln_aec.py',
    'scripts/run_voice_system_gate.py', 'tests/test_dtln_aec.py',
    'tests/test_mind_voice_runtime.py', 'tests/test_python_runtime_lock.py',
    'assets.manifest.json', 'constraints-runtime-win-x64.txt',
    'pylock.runtime-win-x64.toml', 'docs/AI_CONTEXT_MAP.md', 'runtime_wheels/README.md',
]
before = {}
for name in paths:
    source = ROOT / name
    target = OUT / 'before' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    before[name] = hashlib.sha256(source.read_bytes()).hexdigest()
(OUT / 'BEFORE.json').write_text(json.dumps(before, indent=2)+'\n', encoding='utf-8')

owner = 'bindings/webrtc_audio_bindings.cpp'
original = Path('D:/BAXYRuntime/experiments/voice/webrtc174/source/pywebrtc_audio-0.2.0') / owner
diagnostic = Path('D:/BAXYRuntime/experiments/voice/webrtc176/source') / owner
text = diagnostic.read_text(encoding='utf-8')
start = text.index('    py::dict diagnostic_metrics() const {')
end = text.index('    int get_stream_delay_ms()', start)
text = text[:start] + text[end:]
text = text.replace('        .def("diagnostic_metrics", &EchoCanceller::diagnostic_metrics)\n', '')
patch = ''.join(difflib.unified_diff(
    original.read_text(encoding='utf-8').splitlines(keepends=True),
    text.splitlines(keepends=True), fromfile='a/'+owner, tofile='b/'+owner))
target = ROOT / 'runtime_wheels/webrtc-linear-output.patch'
assert not target.exists()
target.write_text(patch, encoding='utf-8', newline='\n')
record = {
    'state': 'native_package_preparation; productive source242 unchanged',
    'hypothesis': 'Export the linear frame from the same original AEC3; no diagnostic metrics or algorithm tuning. Package version0.2.0+baxy.1. Prove exact output parity with254 before productive integration.',
    'originalOwnerSha256': hashlib.sha256(original.read_bytes()).hexdigest(),
    'patchedOwnerSha256': hashlib.sha256(text.encode()).hexdigest(),
    'patchSha256': hashlib.sha256(target.read_bytes()).hexdigest(),
    'previousTurn': 'Status report requested by owner; no implementation progress. Next available action255 performed.',
    'remaining': 'Source integration/locks, owner tests/Fast, actual product/UI/human voice/combined resources, fresh100/100, faults, installation, continuityC04-C09, finalFull and publication outside main.',
}
(OUT / 'PREREG.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
print(json.dumps(record))
