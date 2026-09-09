from pathlib import Path
import datetime
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-ui104'
out.mkdir(exist_ok=False)
previous = json.loads((base / 'astra-ui102/PREREG.json').read_text(encoding='utf-8'))
for name, expected in previous['fixtures'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected
assert not (Path(previous['profile']) / 'filesystem-sandbox/c03-ui100-ausente.txt').exists()
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
assert hashlib.sha256(reg.read_bytes()).hexdigest() == previous['registrationSha256']
with Path(previous['model']).open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == previous['modelSha256']
paths = list(previous['files']) + [
    'src/Baxy.FieldUi/src/components/FieldCenter.tsx',
    'src/Baxy.FieldUi/src/styles/prototype.css',
    'src/Baxy.FieldUi/src/hooks/useEventStream.ts',
    'src/Baxy.FieldUi/ORIGIN.md',
    'src/Baxy.FieldUi/dist/index.html',
    'src/Baxy.FieldUi/dist/assets/index-BdsTtBhL.js',
    'src/Baxy.FieldUi/dist/assets/index-Bvtbe9rc.css']
prereg = {**previous, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'method': 'Source103 presentation only, same eight UI102 cases in the same order. '
        'py main.py, Computer Use Sky, same fixtures/model override. Observe generated '
        'progress above the input before final in Spanish and English; preserve draft '
        'and clear progress on completion; preserve eight useful finals. No fresh human '
        'reserve, no audio acceptance, no promotion, no concurrent build/model.',
    'files': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
monitor = (root / 'scratchpad/c03-ui102-resources.py').read_text(encoding='utf-8')
assert monitor.count('astra-ui102') == 1
(root / 'scratchpad/c03-ui104-resources.py').write_text(monitor.replace('astra-ui102', 'astra-ui104'), encoding='utf-8')
print('UI104 preregistered; unchanged fixtures, model and registration verified.')
