"""Preserve the audio-observation fix and refresh current program attestations."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-audio-observation571'
out.mkdir(exist_ok=False)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

for name in ('src/baxy_mind/llm.py', 'tests/test_c03_request_preservation.py'):
    (out / (Path(name).name + '.before')).write_bytes(subprocess.run(['git', 'show', 'HEAD:' + name], cwd=root, capture_output=True, check=True).stdout)
for suffix in ('baseline', 'focal'):
    (out / (suffix + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-audio571-{suffix}.log').read_bytes())
files = {p.relative_to(root).as_posix(): p for directory in ('experiments/voice_latency', 'scripts', 'src/baxy_mind') for p in (root / directory).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode() + b'\n' + sha(files[name]).encode() + b'\n')
tree = digest.hexdigest()
old = '90b2fedd464bb3a639860d4d91a2912c84915a2b35132cc5907fe440185fdb8a'
for relative in ('experiments/stt_quality/evaluate_reserved_stt.py', 'experiments/stt_quality/audit_fresh_postweight_stt_sources.py'):
    path = root / relative
    text = path.read_text(encoding='utf-8')
    assert old in text
    path.write_text(text.replace(old, tree, 1).replace('# C03 569: current local connectivity questions preserve their catalog operation.', '# C03 571: composer instructions retain nested observed audio state.'), encoding='utf-8', newline='\n')
write(out / 'CURRENT_TREE.json', {'sha256': tree, 'files': len(files), 'before': old, 'historical_pins_unchanged': True})
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'stage': 'After test-first12fail/6pass and focal18pass, before broad owners/Fast/product.',
    'cause': 'Native568:13 carries seen.muted:false but also instructs not to mention mute because it is absent. llm.py9410 checks only top-level situation.observed, while the existing fact projection and validator use _merged_observed including lifted states and serialized mission results.',
    'change': 'Reuse the already computed merged_audio in the missing-mute instruction condition. Remove the redundant top-level read. No new extraction path, facts, guard exemption, template, model setting or desired answer string.',
    'controls': 'Both mute polarities, ES/EN, direct/nested state/applied final/serialized mission result. Absent mute remains withheld and an invented mute state is rejected by the unchanged validator.',
    'source_sha256': sha(root / 'src/baxy_mind/llm.py'), 'next': 'Broad owners, STT declarations, Fast, native/product confirmation and publication. Final Full remains pending.',
})
print(json.dumps({'tree': tree, 'files': len(files)}))
