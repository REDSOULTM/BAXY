"""Seal contiguous human clock context and prepare the whole clock regression."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'CLOCK_CONTEXT781'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not OUT.exists()
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
OUT.mkdir()
sys.path.insert(0, str(ROOT))
from scripts.wake_validation_program_tree import fingerprint_program_tree
prior = read(BASE / 'CLOCK_SCOPE778/PROGRAM.json')
program = fingerprint_program_tree(repository_root=ROOT, source_roots=[ROOT / p for p in prior['roots']])
assert program['pythonFiles'] == 407
paths = ['src/baxy_mind/__main__.py', 'src/baxy_mind/effect_intent.py',
         'tests/test_c03_clock_context.py', 'tests/test_turn_policy.py',
         'experiments/stt_quality/evaluate_reserved_stt.py',
         'experiments/stt_quality/audit_fresh_postweight_stt_sources.py',
         'tests/test_price_v8_veto_damage_by_cause.py', 'src/baxy_mind/llm.py']
for name in paths[4:6]:
    path = ROOT / name
    text = path.read_text(encoding='utf-8')
    assert text.count(prior['sha256']) == 1
    path.write_bytes(text.replace(prior['sha256'], program['sha256']).encode('utf-8'))
path = ROOT / paths[6]
text = path.read_text(encoding='utf-8')
old = hashlib.sha256(subprocess.check_output(['git', 'show', 'HEAD:src/baxy_mind/__main__.py'])).hexdigest()
assert text.count(old) == 1
path.write_bytes(text.replace(old, sha(ROOT / paths[0])).encode('utf-8'))
write(OUT / 'SOURCE_PINS.json', {p: sha(ROOT / p) for p in paths})
write(OUT / 'PROGRAM.json', program)
for name in ['baseline', 'fixed']:
    raw = (Path(os.environ['TEMP']) / f'c03-clock781-context-{name}.log').read_bytes()
    (OUT / (name + '.log')).write_bytes(('\n'.join(line.rstrip() for line in raw.decode('utf-8-sig').splitlines()) + '\n').encode('utf-8'))
driver = (ROOT / 'scratchpad/c03-status-batch779.py').read_text(encoding='utf-8')
driver = driver.replace('779', '782').replace('778', '781').replace('CLOCK_SCOPE781', 'CLOCK_CONTEXT781')
driver = driver.replace("f'clock-variant782-", "f'clock-variant779-")
anchor = 'assert len(panel) == 50 and len({c[\'case_id\'] for c in panel}) == 50\n'
assert driver.count(anchor) == 1
extra = '''
# Six explicit human-style development anchors, each followed by three ellipses.
# Preserve the complete50-case779 panel and all of its original IDs/criteria.
for index, anchor in enumerate([
    'Dime la hora local.', 'What date is it today?', 'Baxy, mostrame the current date.',
    'Could you give me the local time?', '¿Puedes pasarme la fecha?', 'Indícame la hora actual.',
], 1):
    for step, text in enumerate([anchor, '¿Y la fecha?', 'and the time?', '¿Y la hora?'], 1):
        panel.append({'case_id': f'clock-chain782-{index:02d}-{step}', 'group': 'clock',
            'origin': 'assistant development contiguous clock context', 'text': text,
            'supports': [c['case_id'] for c in panel[:15] if c['case_id'].startswith('H')],
            'criterion': panel[0]['criterion']})
assert len(panel) == 74 and len({c['case_id'] for c in panel}) == 74
'''
driver = driver.replace(anchor, anchor + extra)
driver = driver.replace('Complete clock category plus35 development variants', 'Complete50 clock panel plus24 chained context turns')
driver = driver.replace('Complete fifteen-case clock category plus35 declared development variants after shared clock scope781; original clock criterion unchanged.',
    'Complete50-case779 clock panel plus24 declared chained follow-ups after human context781; original clock criterion unchanged.')
driver = driver.replace("'registered_turns': 50", "'registered_turns': 74")
target = ROOT / 'scratchpad/c03-status-batch782.py'
assert not target.exists()
target.write_bytes(driver.encode('utf-8'))
reviewer = (ROOT / 'scratchpad/c03-review-status779.py').read_text(encoding='utf-8')
reviewer = reviewer.replace('779', '782').replace('source778', 'source781').replace('len(panel) == 50', 'len(panel) == 74')
(ROOT / 'scratchpad/c03-review-status782.py').write_bytes(reviewer.encode('utf-8'))
write(OUT / 'PLAN.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'parent': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'evidence': ['STATUS_BATCH779/RESULT.json t50', 'tests/test_turn_policy.py:11839-11877', 'CLOCK_VALUES780/ADJUDICATION.json'],
    'cause': 'The prior user text was re-resolved without its antecedent. Full human history already exists; only the last text was selected.',
    'change': 'Resolve a clock antecedent through a contiguous chain of human nominal clock requests; stop at the first other subject. All other requests retain the immediate previous user text. No assistant prose or remembered clock value grants authority.',
    'baseline': '44fail/22pass/1049deselected,2.07s', 'focused': '67pass/1048deselected,1.29s',
    'new_controls': 62, 'full_new_required': False,
    'pending': 'Whole owner regression/current integrity/Fast, then frozen74 product782. No native model comparison or UI/voice/reserve credit.',
    'unchanged': 'LLM/prompt/recipe/clock-value validator. False noon veto780 and Marka spelling remain open; do not hide them in this context change.',
    'coverage_added': 0, 'survey': {'covered': 26, 'open': 716, 'not_applicable': 0}})
note = ('781 candidato de contexto: antecedente humano a través de elipsis contiguas, con corte al cambiar tema. '
        '67controles enfocados pass, baseline44fail; fuente/receta LLM sin cambios. '
        '8pins yprograma407 sellados; faltan dueñas completas/Fast y782 panel50+24. Mediodía yMarka siguen abiertos.26/716/0.\n\n')
cp = BASE / 'CHECKPOINT.md'; pending = cp.with_suffix('.pending.md')
pending.write_bytes(note.encode('utf-8') + cp.read_bytes()); pending.replace(cp)
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(checkpoint=note.strip(), workStatus='clock_context781_candidate_validation_pending',
    previousGoalTurnClassification='progress',
    previousGoalTurnClassificationReason='Previous turn published778 and100 product/composer cases; current turn repaired the demonstrated chained-context cause in focused owner tests.',
    continuation='Collect current781 owners/integrity/Fast, then74 registered product782. No edits during runs. Noon false-veto and spelling remain separate open findings.')
write(BASE / 'RELEVO_ACTIVO.json', state)
print(json.dumps({'pins': len(paths), 'program': program['sha256'], 'product_turns': 74}))
