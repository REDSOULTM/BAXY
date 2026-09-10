"""Publish diagnostic evidence only; measured787 remains an unadopted candidate."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, data):
    assert not path.exists(), path
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


groups = {
    'INVENTORY_BUDGET786': ['ADJUDICATION.json', 'PARITY.json', 'PINS.json', 'PREREG.json', 'PRIVATE_PINS.json',
                            'PROCESS.json', 'REPORT.md', 'RESPUESTAS_CAMBIADAS.md', 'RESULT.json'],
    'INVENTORY_BUDGET787': ['CANDIDATE.json', 'PLAN.json', 'PROGRAM.json', 'REPORT.md', 'SOURCE_PATCH.diff',
        'SOURCE_PINS.json', 'SOURCE_SNAPSHOT.json', 'VALIDATION.json', 'baseline.log', 'collection-error.log',
        'fast.log', 'first-failure.log', 'fixed.log', 'owners-fixed.log', 'owners.log', 'scope-first.log',
        'scope-second.log', 'validated.log'],
    'INVENTORY_COMPOSER788': ['ADJUDICATION.json', 'PARITY.json', 'PREREG.json', 'PRIVATE_PINS.json',
        'READY.json', 'REPORT.md', 'RESPUESTAS_SINTETICAS.md', 'RESULT.json', 'VALIDATOR_ATTRIBUTION.json'],
}
drivers = ['c03-inventory-budget786.py', 'c03-prepare-inventory-budget786.py', 'c03-record-inventory-budget786.py',
           'c03-seal-inventory-budget787.py', 'c03-preserve-candidate787.py',
           'c03-prepare-composer788.py', 'c03-inventory-composer788.py', 'c03-inventory787-veto-attribution.py',
           'c03-record-composer788.py', 'c03-prepare-evidence-publication788.py']
paths = [BASE / group / name for group, names in groups.items() for name in names]
paths += [ROOT / 'scratchpad' / name for name in drivers]
assert all(p.is_file() and b'\r\n' not in p.read_bytes() for p in paths)
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT).strip()
for group in ['INVENTORY_BUDGET787', 'INVENTORY_COMPOSER788']:
    included = [BASE / group / name for name in groups[group]]
    if group == 'INVENTORY_COMPOSER788':
        included += [ROOT / 'scratchpad' / name for name in drivers]
    pin_path = BASE / group / 'PINS.json'
    write(pin_path, {'files': {p.relative_to(ROOT).as_posix(): sha(p) for p in included}})
    paths.append(pin_path)
paths += [BASE / name for name in ['CHECKPOINT.md', 'HANDOFF.md', 'RELEVO_ACTIVO.json', 'PROSE_SAMPLING785/PUBLICATION.json']]
relative = [p.relative_to(ROOT).as_posix() for p in paths]
subprocess.run(['git', 'add', '--', *relative], cwd=ROOT, check=True)
actual = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT, text=True).splitlines()
assert set(actual) == set(relative)
assert all(hashlib.sha256(subprocess.check_output(['git', 'show', ':' + p], cwd=ROOT)).hexdigest() == sha(ROOT / p) for p in actual)
check = subprocess.run(['git', 'diff', '--cached', '--check'], cwd=ROOT, capture_output=True, text=True)
findings = check.stdout.splitlines()
allowed = [
    'artifacts/comprobaciones/C03/INVENTORY_BUDGET786/RESPUESTAS_CAMBIADAS.md:',
    'artifacts/comprobaciones/C03/INVENTORY_COMPOSER788/RESPUESTAS_SINTETICAS.md:',
    'artifacts/comprobaciones/C03/INVENTORY_BUDGET787/SOURCE_PATCH.diff:',
]
issues = [line for line in findings if not line.startswith('+')]
assert check.returncode in (0, 2)
assert all(line.startswith(tuple(allowed)) and 'trailing whitespace.' in line for line in issues), issues[:20]
checks = {'utc': datetime.now(timezone.utc).isoformat(), 'staged_hashes_verified': len(actual),
          'product_source_changes': [], 'candidate787_adopted': False,
          'git_diff_check_exit': check.returncode, 'trailing_whitespace_findings': len(issues),
          'finding_scope': 'Only exact raw-model text fences and unified-diff evidence containing context/blank-line prefixes. Preserve evidence bytes; no product source whitespace changes.',
          'validation': 'Evidence adjudication/parity59slots and snapshot10hashes/reverse-apply check passed. Existing candidate validation2901pass/1STTskip+121subtests/Fast0 retained; no new source adopted.',
          'staged_files': actual}
check_path = BASE / 'INVENTORY_COMPOSER788/PUBLICATION_CHECKS.json'
write(check_path, checks)
subprocess.run(['git', 'add', '--', check_path.relative_to(ROOT).as_posix()], cwd=ROOT, check=True)
print(json.dumps({'staged': len(actual) + 1, 'whitespace_evidence_findings': len(issues), 'source_adopted': False}))
