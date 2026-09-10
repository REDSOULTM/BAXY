"""Preserve two reproduced checker repairs; native comparisons remain separate."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'INVENTORY_VETO793'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert OUT.exists() and not (OUT / 'PLAN.json').exists()
previous = BASE / 'INVENTORY_IDENTITY791'
prior_pins = read(previous / 'SOURCE_PINS.json')
snapshot = Path(read(previous / 'SOURCE_SNAPSHOT.json')['private_directory'])
assert all(sha(snapshot / p) == h for p, h in prior_pins.items())
for relative in prior_pins:
    path = ROOT / relative
    path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
sys.path.insert(0, str(ROOT))
from scripts.wake_validation_program_tree import fingerprint_program_tree
prior_program = read(previous / 'PROGRAM.json')
program = fingerprint_program_tree(repository_root=ROOT, source_roots=[ROOT / p for p in prior_program['roots']])
assert program['pythonFiles'] == 407
for relative in ['experiments/stt_quality/evaluate_reserved_stt.py', 'experiments/stt_quality/audit_fresh_postweight_stt_sources.py']:
    path = ROOT / relative
    content = path.read_text(encoding='utf-8')
    assert content.count(prior_program['sha256']) == 1
    path.write_bytes(content.replace(prior_program['sha256'], program['sha256']).encode('utf-8'))
price = ROOT / 'tests/test_price_v8_veto_damage_by_cause.py'
content = price.read_text(encoding='utf-8')
assert content.count(prior_pins['src/baxy_mind/llm.py']) == 1
price.write_bytes(content.replace(prior_pins['src/baxy_mind/llm.py'], sha(ROOT / 'src/baxy_mind/llm.py')).encode('utf-8'))


def write(name, value):
    (OUT / name).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


for name in ['baseline', 'first']:
    source = Path(os.environ['TEMP']) / f'c03-inventory-veto793-{name}.log'
    (OUT / (name + '.log')).write_bytes(source.read_bytes().replace(b'\r\n', b'\n'))
assert b'60 failed, 148 passed' in (OUT / 'baseline.log').read_bytes()
assert b'947 passed in 6.21s' in (OUT / 'first.log').read_bytes()
write('PROGRAM.json', program)
write('SOURCE_PINS.json', {p: sha(ROOT / p) for p in prior_pins})
write('PLAN.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'inherits_unadopted': ['INVENTORY_BUDGET787', 'INVENTORY_IDENTITY789', 'INVENTORY_IDENTITY791'],
    'cause': 'Three demonstrated false veto causes in captured792 first drafts: factual no-open phrase, page enumeration quantity, and negated representation of all windows.',
    'change': 'Anchor no-open/no-closed instruction fragments as whole replies; bind quantity introducing observed names to page only without explicit scope; conserve negation of represent/cover/abarcar. No prompt changes.',
    'new_controls': 72, 'baseline': {'failed': 60, 'passed': 148},
    'targeted': {'passed': 947, 'failed': 0, 'skipped': 0, 'seconds': 6.21},
    'first_request_messages_sampling_model_or_deadlines_changed': False,
    'coverage_added': 0, 'candidate_adopted': False, 'full_new': False,
    'full_reason': 'Python-only candidate; final Full and Full upon joint C#/Python adoption remain required.',
    'next': 'Validate21 owners/integrity suites and Fast, then the same50 complete integration tasks794 with registered Qwen. Model selection closed; no more model comparison.',
    'owner_methodology': 'Every model first uses its own native template and documented recipe on all identical tasks; BAXY is then added component by component. Integrated Qwen diagnostics do not select a winner over K2.',
})
note = '793 sellado: tres falsos vetos reparados;72 controles nuevos,947 pass focalizadas y4 primeros borradores capturados entregados exactos en1 llamada. Primeros payloads intactos. Modelo Qwen elegido; pendientes21 suites/Fast y categoría completa794.28/714/0.'
r = read(BASE / 'RELEVO_ACTIVO.json')
r.update(checkpoint=note, workStatus='inventory_veto793_sealed', activeValidation=None,
         previousGoalTurnClassification='progress',
         previousGoalTurnClassificationReason='Published791/792 and model decision ae274b8b. Implemented three demonstrated shared false-veto repairs with72 controls and exact replay of four captured drafts.',
         continuation='Run sealed793 owners and Fast, then same50 complete integration scenarios794. No new model campaign. Preserve source during validation/inference; no survey credit from stub replay.')
(BASE / 'RELEVO_ACTIVO.json').write_bytes((json.dumps(r, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
cp = BASE / 'CHECKPOINT.md'
cp.write_bytes((note + '\n\n').encode('utf-8') + cp.read_bytes())
print(json.dumps({'pins': len(prior_pins), 'program': program['sha256']}))
