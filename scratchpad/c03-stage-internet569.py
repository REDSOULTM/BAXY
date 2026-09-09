"""Preserve baseline, reproduce final test population and refresh only current STT pins."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-internet-query569'
out.mkdir(exist_ok=True)
assert not (out / 'PREREG.json').exists()
owner = root / 'src/baxy_mind/effect_intent.py'
candidate = owner.read_bytes()
assert b'def _local_internet_connection_query' in candidate
(out / 'effect_intent.py.candidate').write_bytes(candidate)
baseline = subprocess.run(['git', 'show', 'HEAD:src/baxy_mind/effect_intent.py'], cwd=root, capture_output=True, check=True).stdout
(out / 'effect_intent.py.before').write_bytes(baseline)
(out / 'test_c03_internet_state.py').write_bytes((root / 'tests/test_c03_internet_state.py').read_bytes())
if not (out / 'BASELINE.log').exists():
    try:
        owner.write_bytes(baseline)
        with (out / 'BASELINE.log').open('w', encoding='utf-8', newline='\n') as log:
            result = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'pytest', 'tests/test_c03_internet_state.py', '-q', '--tb=short'], cwd=root, stdout=log, stderr=subprocess.STDOUT)
        assert result.returncode == 1
    finally:
        owner.write_bytes(candidate)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

files = {p.relative_to(root).as_posix(): p for directory in ('experiments/voice_latency', 'scripts', 'src/baxy_mind') for p in (root / directory).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode() + b'\n' + sha(files[name]).encode() + b'\n')
tree = digest.hexdigest()
old = '5a3d37d79c0e4b7366c3d7857b699a32c9d6e1b84df9d794f89bc3dea890415d'
for relative in ('experiments/stt_quality/evaluate_reserved_stt.py', 'experiments/stt_quality/audit_fresh_postweight_stt_sources.py'):
    path = root / relative
    text = path.read_text(encoding='utf-8')
    assert old in text
    path.write_text(text.replace(old, tree, 1).replace('# C03 555: contextual interpretation is not a visible-answer fallback.', '# C03 569: current local connectivity questions preserve their catalog operation.'), encoding='utf-8', newline='\n')
write(out / 'CURRENT_TREE.json', {'sha256': tree, 'files': len(files), 'before': old, 'historical_pins_unchanged': True})
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'stage': 'After initial diagnostic and focal22pass; before broad owners/Fast/product. Final test population replayed on exact HEAD source for a comparable baseline; no blinded preregistration claim.',
    'cause': 'Shared product568 English local internet question becomes web.search in deterministic domain recognition; planner later proposes network.status/wifi.status but result remains failed web search. The internet noun was treated as web-content authority before local state resolution.',
    'change': 'A bounded whole-clause local connectivity grammar ES/EN resolves only network.status in the existing catalog reader, with same negative/meta/other-device gates. Whole clause preserves compound conservation; missing authenticated operation returns no substitute. New speech-act shape also enters existing direct-request gate. No visible template, new model or new execution path.',
    'controls': 'Ten local questions including different machine nouns, inversion and explicit checks; two absent catalog controls; real ES/EN web searches; theory, movie, phone, negation, quoted note and compound clock.',
    'source_sha256': sha(owner), 'test_sha256': sha(root / 'tests/test_c03_internet_state.py'),
    'next': 'Owner suites, current STT declaration tests, Fast, shared product repair evidence and publication. Python source only; final Full remains required.',
})
print(json.dumps({'tree': tree, 'files': len(files)}))
