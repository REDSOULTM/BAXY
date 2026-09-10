"""Run sealed791 owners and Fast, preserving every terminal result."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/comprobaciones/C03/INVENTORY_IDENTITY791'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
pins = read(OUT / 'SOURCE_PINS.json')
assert all(sha(ROOT / p) == h for p, h in pins.items())
assert not (OUT / 'VALIDATION.json').exists()
previous = read(OUT.parent / 'INVENTORY_BUDGET787/VALIDATION.json')
files = previous['files'] + ['tests/test_c03_inventory_identity_coverage.py']
command = [sys.executable, '-X', 'utf8', '-m', 'pytest', *files, '-q']
started = time.monotonic()
with (OUT / 'validated.log').open('w', encoding='utf-8', newline='\n') as log:
    process = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
result = {'utc': datetime.now(timezone.utc).isoformat(), 'python_command': command,
          'python_exit_code': process.returncode, 'fast_command': ['powershell.exe', '-NoProfile', '-File',
              'scripts/test_source_quality.ps1', '-Mode', 'Fast'], 'fast_exit_code': None,
          'source_pins_unchanged': all(sha(ROOT / p) == h for p, h in pins.items()),
          'new_controls': 72, 'candidate_adopted': False, 'full_new': False}
if process.returncode == 0 and result['source_pins_unchanged']:
    with (OUT / 'fast.log').open('w', encoding='utf-8', newline='\n') as log:
        fast = subprocess.run(result['fast_command'], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    result['fast_exit_code'] = fast.returncode
for name in ['validated.log', 'fast.log']:
    path = OUT / name
    if path.exists():
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
content = (OUT / 'validated.log').read_text(encoding='utf-8')
summary = re.search(r'(\d+) passed, (\d+) skipped, (\d+) subtests passed in ([\d.]+)s', content)
if summary:
    result.update(passed=int(summary[1]), environmental_skips=int(summary[2]), subtests_passed=int(summary[3]),
                  python_seconds=float(summary[4]), skip='Private STT inputs absent; not a voice pass.')
result.update(total_seconds=time.monotonic() - started,
              source_pins_unchanged=all(sha(ROOT / p) == h for p, h in pins.items()))
(OUT / 'VALIDATION.json').write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print(json.dumps(result), flush=True)
assert result['python_exit_code'] == result['fast_exit_code'] == 0 and result['source_pins_unchanged']
