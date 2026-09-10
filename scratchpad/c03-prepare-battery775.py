"""Freeze the observed-battery actor repair and its current declarations."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'BATTERY_ACTOR775'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not OUT.exists()
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
OUT.mkdir()
sys.path.insert(0, str(ROOT))
from scripts.wake_validation_program_tree import fingerprint_program_tree
prior = read(BASE / 'MACHINE_SCOPE773/PROGRAM.json')
program = fingerprint_program_tree(repository_root=ROOT, source_roots=[ROOT / p for p in prior['roots']])
assert program['pythonFiles'] == 407
paths = ['src/baxy_mind/llm.py', 'tests/test_c03_battery_actor.py',
         'experiments/stt_quality/evaluate_reserved_stt.py',
         'experiments/stt_quality/audit_fresh_postweight_stt_sources.py',
         'tests/test_price_v8_veto_damage_by_cause.py']
for name in paths[2:4]:
    path = ROOT / name
    text = path.read_text(encoding='utf-8')
    assert text.count(prior['sha256']) == 1
    path.write_bytes(text.replace(prior['sha256'], program['sha256']).encode('utf-8'))
path = ROOT / paths[-1]
text = path.read_text(encoding='utf-8')
previous_llm = read(BASE / 'MACHINE_SCOPE773/SOURCE_PINS.json')[paths[0]]
assert text.count(previous_llm) == 1
path.write_bytes(text.replace(previous_llm, sha(ROOT / paths[0])).encode('utf-8'))
assert all(b'\r\n' not in (ROOT / p).read_bytes() for p in paths)
write(OUT / 'SOURCE_PINS.json', {p: sha(ROOT / p) for p in paths})
write(OUT / 'PROGRAM.json', program)
for source, target in [('owners', 'owners-language-fixture-error.log'), ('owners-final', 'owners.log')]:
    raw = (Path(os.environ['TEMP']) / f'c03-battery-actor775-{source}.log').read_bytes()
    (OUT / target).write_bytes(raw.replace(b'\r\n', b'\n'))
write(OUT / 'PLAN.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'parent': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'evidence': ['STATUS_BATCH774/RESULT.json H0665', 'astra-cpu-repair-generalization580/RESULT.md',
                 'tests/test_c03_cpu_actor.py', 'tests/test_c03_network_actor_recovery.py'],
    'diagnosis': 'wrong_machine_actor classifier only considered CPU observation, so battery first-person ownership escaped the existing shared repair.',
    'change': 'Classify direct battery possession/percentage/charging in first person only with a nonempty battery observation; reuse the same actor repair without changing its prompt/sampler/budget.',
    'owners_before_seal': {'passed': 261, 'failed': 0, 'skipped': 0, 'seconds': 2.53, 'new_cases': 56},
    'initial_test_error': '16 English actor fixtures used ambiguous Battery status, which the language reader resolved to Spanish. Replaced the fixture question with the unambiguous real774 How much battery is left; no language source change.',
    'pending': 'Current integrity/Fast and real local composer on50 declared synthetic battery scenarios. No adoption or survey coverage yet.',
    'full_new_required': False, 'coverage_added': 0,
    'survey': {'covered': 26, 'open': 716, 'not_applicable': 0}})
note = ('775 candidato: clasificación wrong_machine_actor incluye batería observada y reutiliza reparación existente sin cambiar prompt/sampler/presupuesto. '
        '261owners/0skip/2,53s,56nuevos;16fallos iniciales eran pregunta inglesa ambigua enfixture, conservados. '
        '5pins yprograma407 sellados. Faltan integridad/Fast y50fixtures modelo local de valores/carga/ausencia. No inferencia activa.26/716/0.\n\n')
cp = BASE / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
pending.write_bytes(note.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(checkpoint=note.strip(), workStatus='battery_actor775_candidate_validation_pending',
             previousGoalTurnClassification='progress',
             previousGoalTurnClassificationReason='Published773 input-scope repair, adjudicated774 complete battery category and located independent actor defect; no owner blocker.',
             continuation='Validate775 current pins/Fast, then50 declared synthetic battery scenarios in direct registered composer. Do not infer product UI/voice or reserve credit.')
write(BASE / 'RELEVO_ACTIVO.json', state)
print(json.dumps({'pins': len(paths), 'program': program}))
