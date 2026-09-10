"""Publish only this diagnostic's evidence; preserve executed bytes before LF."""
from pathlib import Path
from datetime import datetime, timezone
import base64
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'INVENTORY_PROJECTION759'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert git('branch', '--show-current').decode().strip() == 'Goal-c03'
assert git('rev-parse', 'main').decode().strip() == '5f572ee1b48cb5e2543ee5e06510e51057c9c845'
assert not git('diff', '--cached', '--name-only').strip()
assert not git('diff', '--name-only', '--', 'src', 'tests', 'scripts', 'main.py').strip()
pins751 = json.loads((BASE / 'WINDOW_INVENTORY751/SOURCE_PINS.json').read_text(encoding='utf-8-sig'))
assert all(sha((ROOT / path).read_bytes()) == digest for path, digest in pins751.items())

files = []
groups = {
    'COMPOSE_BOUNDARY753': ['DIAGNOSIS.json', 'EXIT.json', 'OBSERVER_PREFLIGHT.json', 'PREREG.json', 'PROCESS.json', 'RESOURCES.json'],
    'INVENTORY_PROMPT754': ['PREREG.json', 'PROCESS.json', 'RESULT.json'],
    'INVENTORY_PROMPT755': ['PREREG.json', 'PROCESS.json', 'RESULT.json'],
    'INVENTORY_OUTPUT756': ['PREREG.json', 'PROCESS.json', 'RESULT.json'],
    'INVENTORY_PROJECTION757': ['PREREG.json', 'PROCESS.json', 'RESULT.json', 'ADJUDICATION.json'],
    'INVENTORY_PROJECTION758': ['PREREG.json', 'PROCESS.json', 'RESULT.json', 'ADJUDICATION.json'],
    'INVENTORY_PROJECTION759': ['PREREG.json', 'PROCESS.json', 'RESULT.json', 'ADJUDICATION.json', 'REPORT.md'],
}
for group, names in groups.items():
    files.extend(BASE / group / name for name in names)
drivers = [
    'c03-compose-boundary753.py', 'c03-compose753-hook/sitecustomize.py',
    'c03-observer-preflight753.py', 'c03-inventory-prompt754.py',
    'c03-inventory-prompt755.py', 'c03-inventory-output756.py',
    'c03-inventory-projection757.py', 'c03-adjudicate-inventory757.py',
    'c03-prepare-inventory758.py', 'c03-inventory-projection758.py',
    'c03-prepare-inventory759.py', 'c03-inventory-projection759.py',
    'c03-record-inventory759.py', 'c03-seal-inventory759.py',
]
driver_paths = [ROOT / 'scratchpad' / name for name in drivers]
snapshots = {}
for path in driver_paths:
    data = path.read_bytes()
    snapshots[path.relative_to(ROOT).as_posix()] = {
        'executed_or_authored_sha256': sha(data), 'original_bytes_base64': base64.b64encode(data).decode(),
    }
write(OUT / 'RUNNER_SNAPSHOTS.json', snapshots)
files.extend(driver_paths)
files.extend([OUT / 'RUNNER_SNAPSHOTS.json', BASE / 'STATUS_BATCH752B/PUBLICATION.json'])
# These are new public artifacts only. Historical seals and source stay untouched.
for path in files:
    data = path.read_bytes()
    path.write_bytes(data.replace(b'\r\n', b'\n'))
pins = {path.relative_to(ROOT).as_posix(): sha(path.read_bytes()) for path in files}
write(OUT / 'PINS.json', pins)
write(OUT / 'PUBLICATION_PRECHECK.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'source751_pins_verified': len(pins751),
    'new_public_pins': len(pins), 'product_source_edited': False,
    'source_tests_rerun': False, 'reason': 'Evidence-only diagnostics; prior source validation unchanged.',
    'main_unchanged': True, 'survey_counts': {'covered': 26, 'open': 716, 'not_applicable': 0},
    'goal_complete': False,
})
files.extend([OUT / 'PINS.json', OUT / 'PUBLICATION_PRECHECK.json'])
files.extend(BASE / name for name in ['CHECKPOINT.md', 'HANDOFF.md', 'RELEVO_ACTIVO.json'])
relative = [path.relative_to(ROOT).as_posix() for path in files]
git('add', '--', *relative)
staged = set(git('diff', '--cached', '--name-only', '-z').decode().strip('\0').split('\0'))
assert staged == set(relative), (staged - set(relative), set(relative) - staged)
for path, digest in pins.items():
    assert sha(git('show', ':' + path)) == digest, path
assert not git('diff', '--cached', '--check').strip()
print(json.dumps({'staged_files': len(staged), 'public_pins_verified': len(pins), 'source_pins_verified': len(pins751)}))
