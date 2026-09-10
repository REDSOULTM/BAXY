"""Check current source/index, private evidence and preserved predecessor seals."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-audit-focus680-682.py').read_text(encoding='utf-8')
start = source.index('specs = [')
end = source.index('pins = 0', start)
source = source[:start]+'''specs = [
    ('astra-continuity-source703', None),
    ('astra-status-batch704', 'C03-status-batch704-private'),
]
'''+source[end:]
source = source.replace('astra-focus-subject-source680/RESULT.json', 'astra-continuity-source703/RESULT.json')
source = source.replace('len(files) == 405', 'len(files) == 406')
exec(compile(source, __file__, 'exec'))
for name, expected in record['sources'].items():
    staged = subprocess.check_output(['git', 'show', ':'+name], cwd=root)
    assert hashlib.sha256(staged).hexdigest() == expected, ('source_index', name)
plan = base / 'STATUS_BATCH704_PLAN.json'
assert sha(plan) == read(base / 'astra-status-batch704/RESULT.json')['plan_sha256']
for path, expected in [(plan, sha(plan)),
                       (root / 'scratchpad/c03-status704-hook/sitecustomize.py', read(plan)['instrumentation_sha256'])]:
    assert sha(path) == expected
    staged = subprocess.check_output(['git', 'show', ':'+path.relative_to(root).as_posix()], cwd=root)
    assert hashlib.sha256(staged).hexdigest() == expected, ('index', str(path))
for name in ['astra-machine-actor-source702', 'astra-status-batch702']:
    for filename, expected in read(base / name / 'PINS.json').items():
        assert sha(base / name / filename) == expected, ('prior_seal', name, filename)
print({'source_index': True, 'plan_observer_index': True, 'source702_and_product702_seals_intact': True})
