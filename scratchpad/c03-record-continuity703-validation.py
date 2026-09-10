"""Record successful owner validation without erasing the initial fixture failures."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-continuity-source703'
temp = Path(os.environ['TEMP'])
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
prereg = read(out / 'PREREG.json')
assert not (out / 'VALIDATED.json').exists()
sources = {name: sha(root / name) for name in prereg['sources']}
changed = [name for name in sources if sources[name] != prereg['sources'][name]]
assert changed == ['tests/Baxy.Integration.Tests/MindPlanSessionTests.cs'], changed
summaries = {}
for suffix in ['owners', 'owners2']:
    path = temp / f'c03-continuity703-{suffix}.log'
    text = path.read_text(encoding='utf-8-sig')
    match = re.search(r'Con error:\s+(\d+),\s+Superado:\s+(\d+),\s+Omitido:\s+(\d+),\s+Total:\s+(\d+)', text)
    assert match, suffix
    failed, passed, skipped, total = map(int, match.groups())
    assert failed == (4 if suffix == 'owners' else 0)
    summaries[suffix] = {'failed': failed, 'passed': passed, 'skipped': skipped, 'total': total}
    (out / (suffix.upper()+'.log')).write_bytes(path.read_bytes())
gate = temp / 'c03-continuity703-fast.log'
assert 'source_quality_gate_passed: mode=Fast' in gate.read_text(encoding='utf-8-sig')
(out / 'FAST.log').write_bytes(gate.read_bytes())
validated = {'utc': datetime.now(timezone.utc).isoformat(), 'sources': sources,
             'python_tree_sha256': prereg['python_tree_sha256'], 'python_files': prereg['python_files'],
             'owner_results': summaries, 'fast_exit': 0, 'full703_run': False,
             'fixture_correction': {'file': changed[0], 'before_sha256': prereg['sources'][changed[0]],
                                    'after_sha256': sources[changed[0]],
                                    'reason': 'The test used a noncanonical43-character base64url token and serializer-selected date precision. It now constructs a canonical32-byte token and an explicit round-trip O UTC expiry, as required by the unchanged confirmation parser. All four clean/reconciliation/uncertainty permutations remain.'},
             'adopted': False, 'product704_pending': True, 'new_coverage': 0, 'goal_complete': False}
(out / 'VALIDATED.json').write_text(json.dumps(validated, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(summaries)
