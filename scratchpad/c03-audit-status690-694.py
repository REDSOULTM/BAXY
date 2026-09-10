"""Audit staged693 source and paired evidence before publishing on Goal-c03."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-audit-focus680-682.py').read_text(encoding='utf-8')
start = source.index('specs = [')
end = source.index('pins = 0', start)
source = source[:start]+'''specs = [
    ('astra-native-measurements690', 'C03-native-measurements690-private'),
    ('astra-native-measurement-units691', 'C03-native-measurement-units691-private'),
    ('astra-shared-status-source693', None),
    ('astra-status-batch694', 'C03-status-batch694-private'),
]
'''+source[end:]
source = source.replace('astra-focus-subject-source680/RESULT.json', 'astra-shared-status-source693/RESULT.json')
source = source.replace('len(files) == 405', 'len(files) == 406')
exec(compile(source, __file__, 'exec'))
for name, expected in read(base/'astra-shared-status-source693/RESULT.json')['sources'].items():
    staged = subprocess.check_output(['git', 'show', ':'+name], cwd=root)
    assert hashlib.sha256(staged).hexdigest() == expected, ('source_index', name)
plan = base/'STATUS_BATCH694_PLAN.json'
expected = read(base/'astra-status-batch694/RESULT.json')['plan_sha256']
assert sha(plan) == expected
staged = subprocess.check_output(['git', 'show', ':'+plan.relative_to(root).as_posix()], cwd=root)
assert hashlib.sha256(staged).hexdigest() == expected, 'plan_index'
hook = 'scratchpad/c03-status694-hook/sitecustomize.py'
staged = subprocess.check_output(['git', 'show', ':'+hook], cwd=root)
assert hashlib.sha256(staged).hexdigest() == read(plan)['instrumentation_sha256'], 'observer_index'
for name, expected in read(base/'COVERAGE_WORKBOARD692_PINS.json').items():
    path = root/name if name.startswith('scratchpad/') else base/name
    assert sha(path) == expected, name
    staged = subprocess.check_output(['git', 'show', ':'+path.relative_to(root).as_posix()], cwd=root)
    assert hashlib.sha256(staged).hexdigest() == expected, ('index', name)
print({'workboard692_pins': True})
