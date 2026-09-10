"""Verify the exact staged source and the preserved control/product evidence."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-audit-focus680-682.py').read_text(encoding='utf-8')
start = source.index('specs = [')
end = source.index('pins = 0', start)
source = source[:start]+'''specs = [
    ('astra-machine-actor701-baseline', 'C03-machine-actor701-baseline-private'),
    ('astra-machine-actor701-candidate', 'C03-machine-actor701-candidate-private'),
    ('astra-machine-actor-source702', None),
    ('astra-status-batch702', 'C03-status-batch702-private'),
]
'''+source[end:]
source = source.replace('astra-focus-subject-source680/RESULT.json', 'astra-machine-actor-source702/RESULT.json')
source = source.replace('len(files) == 405', 'len(files) == 406')
exec(compile(source, __file__, 'exec'))
for name, expected in read(base / 'astra-machine-actor-source702/RESULT.json')['sources'].items():
    staged = subprocess.check_output(['git', 'show', ':'+name], cwd=root)
    assert hashlib.sha256(staged).hexdigest() == expected, ('source_index', name)
plan = base / 'STATUS_BATCH702_PLAN.json'
assert sha(plan) == read(base / 'astra-status-batch702/RESULT.json')['plan_sha256']
for path, expected in [(plan, sha(plan)),
                       (root / 'scratchpad/c03-status702-hook/sitecustomize.py', read(plan)['instrumentation_sha256'])]:
    assert sha(path) == expected
    staged = subprocess.check_output(['git', 'show', ':'+path.relative_to(root).as_posix()], cwd=root)
    assert hashlib.sha256(staged).hexdigest() == expected, ('index', str(path))
for name in ['astra-status-batch694', 'astra-shared-status-source693']:
    for filename, expected in read(base / name / 'PINS.json').items():
        assert sha(base / name / filename) == expected, ('prior_seal', name, filename)
print({'source_index': True, 'plan_observer_index': True, 'prior693_694_seals_intact': True})
