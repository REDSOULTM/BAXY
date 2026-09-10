"""Seal the identity-count repair and inherited787 before final validation."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'INVENTORY_IDENTITY789'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert not OUT.exists()
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT).strip()
source787 = read(BASE / 'INVENTORY_BUDGET787/SOURCE_PINS.json')
snapshot = Path(read(BASE / 'INVENTORY_BUDGET787/SOURCE_SNAPSHOT.json')['private_directory'])
assert all(sha(snapshot / p) == h for p, h in source787.items())
paths = list(source787) + ['tests/test_c03_inventory_identity_coverage.py',
                          'tests/test_c03_inventory_semantic_projection.py', 'tests/test_c03_window_inventory.py']
for name in paths:
    p = ROOT / name
    p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n'))
sys.path.insert(0, str(ROOT))
from scripts.wake_validation_program_tree import fingerprint_program_tree
prior = read(BASE / 'INVENTORY_BUDGET787/PROGRAM.json')
program = fingerprint_program_tree(repository_root=ROOT, source_roots=[ROOT / p for p in prior['roots']])
assert program['pythonFiles'] == 407
for name in ['experiments/stt_quality/evaluate_reserved_stt.py', 'experiments/stt_quality/audit_fresh_postweight_stt_sources.py']:
    p = ROOT / name
    text = p.read_text(encoding='utf-8')
    assert text.count(prior['sha256']) == 1
    p.write_bytes(text.replace(prior['sha256'], program['sha256']).encode('utf-8'))
assert sha(ROOT / 'src/baxy_mind/llm.py') == source787['src/baxy_mind/llm.py']
OUT.mkdir()


def write(name, data):
    (OUT / name).write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


for name in ['baseline', 'first', 'owners1', 'first-failure', 'owners2']:
    source = Path(os.environ['TEMP']) / f'c03-inventory-identity789-{name}.log'
    (OUT / (name + '.log')).write_bytes(source.read_bytes().replace(b'\r\n', b'\n'))
assert b'80 failed, 3 passed in 1.17s' in (OUT / 'baseline.log').read_bytes()
assert b'2973 passed, 121 subtests passed in 15.69s' in (OUT / 'owners2.log').read_bytes()
write('PROGRAM.json', program)
write('SOURCE_PINS.json', {p: sha(ROOT / p) for p in paths})
write('PLAN.json', {'utc': datetime.now(timezone.utc).isoformat(), 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'inherits_unadopted': 'INVENTORY_BUDGET787', 'first_request_messages_and_sampling_changed': False,
    'cause': '788 lists five titles for twenty observed entries without exact multiplicities. Numeric scope correctness had hidden missing identities.',
    'change': 'Existing window fact feedback conserves requested identity counts; explicit group cardinalities bind to observed names, not global totals. Existing retry gets structured missing/contradictory facts. No new narrator, prompt template or model-specific branch.',
    'new_controls': 89, 'baseline': {'failed': 80, 'passed': 3, 'later_controls': 6},
    'owners': {'passed': 2973, 'failed': 0, 'skipped': 0, 'subtests_passed': 121, 'seconds': 15.69},
    'existing_fixture_repairs': 'Seven chronology controls and one process-uncertainty control now include observed identities so their positive answer is complete; original factual assertions and expected outcomes unchanged. Initial8 failures preserved.',
    'validation_pending': 'Sealed20 previous suites plus new owner, integrity and Fast; then same50 real composer cases790 with full attempt logging, separately scored.',
    'coverage_added': 0, 'candidate_adopted': False, 'full_new': False,
    'full_reason': 'Python-only repair; C#764 unchanged; goal requires final Full and Full on joint C#/Python adoption.'})
note = '789 candidato sellado:89controles nuevos,2973pass/0skip+121subtests/15,69s. Identidades y multiplicidad en verificador existente; grupos exactos y listas completos permitidos, sin cambiar primerprompt/sampler.787histórico preservado;13pins/programa407 nuevos. Pendientes integridad/Fast final y50casos790.28/714/0.'
r = read(BASE / 'RELEVO_ACTIVO.json')
r.update(checkpoint=note, workStatus='inventory_identity789_sealed', activeValidation=None,
         previousGoalTurnClassification='progress', previousGoalTurnClassificationReason='Previous turn completed788 adjudication, proved baseline veto attribution, preserved787 source and published evidence64b49388. Current turn repairs the identified coverage gap with89 controls and2973 owner passes.',
         continuation='Run sealed789 final owners/integrity/Fast. Do not edit source during validation or790 inference. Use frozen50 cases788, same first payloads and deadlines. Measure actual complete final quality before adoption.')
(BASE / 'RELEVO_ACTIVO.json').write_bytes((json.dumps(r, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
cp = BASE / 'CHECKPOINT.md'
cp.write_bytes((note + '\n\n').encode('utf-8') + cp.read_bytes())
print(json.dumps({'pins': len(paths), 'program': program['sha256']}))
