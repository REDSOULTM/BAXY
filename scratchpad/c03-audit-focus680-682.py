"""Verify source, evidence, privacy pins, survey and inactive product before publication."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import psutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
home = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
specs = [
    ('astra-survey-focus679', 'C03-survey-focus679-private'),
    ('astra-survey-focus681', 'C03-survey-focus681-private'),
    ('astra-native-mixed-focus682', 'C03-native-mixed-focus682-private'),
    ('astra-focus-subject-source680', None),
]
pins = 0
for name, private_name in specs:
    out = base / name
    for filename, expected in read(out / 'PINS.json').items():
        assert sha(out / filename) == expected, (name, filename)
        indexed = subprocess.check_output(['git', 'show', ':' + (out / filename).relative_to(root).as_posix()], cwd=root)
        assert hashlib.sha256(indexed).hexdigest() == expected, ('index', name, filename)
        pins += 1
    result = read(out / 'RESULT.json')
    for filename, expected in result['private_hashes'].items():
        assert sha(home / private_name / filename) == expected, (name, filename)
    if 'corrected679_private_hashes' in result:
        for filename, expected in result['corrected679_private_hashes'].items():
            assert sha(home / 'C03-survey-focus679-private' / filename) == expected
record = read(base / 'astra-focus-subject-source680/RESULT.json')
for name, expected in record['sources'].items():
    assert sha(root / name) == expected, name
files = {p.relative_to(root).as_posix(): p for folder in ['experiments/voice_latency', 'scripts', 'src/baxy_mind']
         for p in (root / folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode() + b'\n' + sha(files[name]).encode() + b'\n')
assert len(files) == 405 and digest.hexdigest() == record['python_tree_sha256']
for name in ['audit_fresh_postweight_stt_sources.py', 'evaluate_reserved_stt.py']:
    assert (root / 'experiments/stt_quality' / name).read_bytes().count(digest.hexdigest().encode()) == 1
assert sha(home / 'C03-survey-requirements336-private/requirements.jsonl') == '237c14900a9e36e2e5f6071f132ad916a234ecb39a77e0dd497ef2565eceb2b7'
assert sha(Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json') == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
assert subprocess.check_output(['git', 'rev-parse', 'main'], cwd=root, text=True).strip() == '5f572ee1b48cb5e2543ee5e06510e51057c9c845'
assert subprocess.check_output(['git', 'branch', '--show-current'], cwd=root, text=True).strip() == 'Goal-c03'
assert not [p.info for p in psutil.process_iter(['pid', 'name']) if (p.info['name'] or '').lower() in {'baxy.exe', 'baxy.app.exe', 'llama-server.exe'}]
print({'pins': pins, 'sources_and_tree': True, 'survey_unchanged': True, 'runtime_unchanged': True, 'main_intact': True, 'product_closed': True})
