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
OUT = BASE / 'INVENTORY_IDENTITY791'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert not OUT.exists()
previous = BASE / 'INVENTORY_IDENTITY789'
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
assert sha(ROOT / 'src/baxy_mind/llm.py') == prior_pins['src/baxy_mind/llm.py']
OUT.mkdir()


def write(name, value):
    (OUT / name).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


for name in ['baseline', 'first']:
    source = Path(os.environ['TEMP']) / f'c03-inventory-identity791-{name}.log'
    (OUT / (name + '.log')).write_bytes(source.read_bytes().replace(b'\r\n', b'\n'))
assert b'72 failed, 89 passed' in (OUT / 'baseline.log').read_bytes()
assert b'808 passed in 5.30s' in (OUT / 'first.log').read_bytes()
write('PROGRAM.json', program)
write('SOURCE_PINS.json', {p: sha(ROOT / p) for p in prior_pins})
write('PLAN.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'inherits_unadopted': ['INVENTORY_BUDGET787', 'INVENTORY_IDENTITY789'],
    'cause': 'Two reproduced checker errors in INVENTORY_COMPOSER790/REVIEW_FINDINGS.json.',
    'change': 'Count a title before sentence-ending punctuation after protecting opaque names; exclude a known process annotation from the count of independent unnamed windows.',
    'new_controls': 72, 'baseline': {'failed': 72, 'passed': 89},
    'targeted': {'passed': 808, 'failed': 0, 'skipped': 0, 'seconds': 5.30},
    'first_request_messages_sampling_model_or_deadlines_changed': False,
    'coverage_added': 0, 'candidate_adopted': False, 'full_new': False,
    'full_reason': 'Python-only candidate; final Full and Full upon joint C#/Python adoption remain required.',
    'next': 'Validate all21 owners/integrity suites and Fast, then paired diagnostic792 removes only rejected_draft from factual repair at the outgoing HTTP boundary. No runtime prompt adoption without evidence.',
    'owner_methodology': 'Every model first uses its own native template and documented recipe on all identical tasks; BAXY is then added component by component. Integrated Qwen diagnostics do not select a winner over K2.',
})
note = ('791 candidato sellado: reparados los dos errores reproducidos del verificador de inventario; '
        '72 controles nuevos, baseline 72 fallos/89 pass, focalizadas 808 pass/0 skips. '
        'Primer prompt, modelo, sampler y plazos intactos. Pendientes 21 suites y Fast. '
        'El dueño recalca separar el modelo nativo de las transformaciones BAXY; 792 será una ablación de integración, no ranking de modelos. Encuesta 28/714/0.')
r = read(BASE / 'RELEVO_ACTIVO.json')
r.update(checkpoint=note, workStatus='inventory_identity791_sealed', activeValidation=None,
         previousGoalTurnClassification='progress',
         previousGoalTurnClassificationReason='Preserved789 and790; implemented two demonstrated checker repairs and72 controls,808 targeted passes. Native/integrated methodology reviewed against699 and737.',
         continuation='Run sealed791 owners and Fast. Keep source unchanged; then compare same50 composer tasks in both arms of diagnostic792, removing only rejected_draft in arm B. No native-model or survey acceptance inferred.')
(BASE / 'RELEVO_ACTIVO.json').write_bytes((json.dumps(r, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
cp = BASE / 'CHECKPOINT.md'
cp.write_bytes((note + '\n\n').encode('utf-8') + cp.read_bytes())
print(json.dumps({'pins': len(prior_pins), 'program': program['sha256']}))
