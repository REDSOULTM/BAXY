"""Freeze shared clock recognition and prepare one full 50-turn product panel."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'CLOCK_SCOPE778'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not OUT.exists()
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
OUT.mkdir()
sys.path.insert(0, str(ROOT))
from scripts.wake_validation_program_tree import fingerprint_program_tree
prior = read(BASE / 'BATTERY_ACTOR775/PROGRAM.json')
program = fingerprint_program_tree(repository_root=ROOT, source_roots=[ROOT / p for p in prior['roots']])
assert program['pythonFiles'] == 407
paths = ['src/baxy_mind/effect_intent.py', 'tests/test_c03_local_clock_scope.py',
         'experiments/stt_quality/evaluate_reserved_stt.py',
         'experiments/stt_quality/audit_fresh_postweight_stt_sources.py',
         'src/baxy_mind/llm.py']
for name in paths[2:4]:
    path = ROOT / name
    source = path.read_text(encoding='utf-8')
    assert source.count(prior['sha256']) == 1
    path.write_bytes(source.replace(prior['sha256'], program['sha256']).encode('utf-8'))
write(OUT / 'SOURCE_PINS.json', {p: sha(ROOT / p) for p in paths})
write(OUT / 'PROGRAM.json', program)
for name in ['baseline', 'baseline2', 'owners', 'boundary']:
    raw = (Path(os.environ['TEMP']) / f'c03-clock778-{name}.log').read_bytes()
    # Public logs remove terminal-only trailing whitespace; originals stay in TEMP.
    normalized = '\n'.join(line.rstrip() for line in raw.decode('utf-8-sig').splitlines()) + '\n'
    (OUT / f'{name}.log').write_bytes(normalized.encode('utf-8'))

variants = [
    'Muéstrame la fecha actual.', 'Pásame la fecha de hoy.', 'Enséñame la hora local.',
    'Indícame la fecha de hoy.', 'Comprueba la hora local.',
    'Baxy, mostrame la hora.', 'Por favor, mostrame la fecha.',
    '¿Puedes pasarme la hora?', 'Baxy, dame la fecha.',
    'Decime la hora actual.', 'Show me the current date.',
    'Give me the local time.', 'Check the current local time.',
    "Tell me today's date.", 'What is the local time?',
    'Baxy, show me the current date.', 'Please give me the local time.',
    'Could you show me the current date?', 'Tell me the current local time.',
    'What date is it today?', 'Mostrame the current date.', 'Show me la hora actual.',
    'Baxy, give me la fecha de hoy.', 'Por favor, show me the local time.',
    'Dime qué hora es.', 'Hola, dime qué fecha es hoy.',
    'Ahora mismo, indícame la hora local.', 'Responde en inglés: mostrame la fecha.',
    'Answer in Spanish: show me the current date.',
    'What time does this computer show?', '¿Qué hora marca mi PC?',
    'Necesito saber la hora actual.', 'I need to know the time right now, what is it?',
    '¿Y la fecha?', '¿Y la hora?',
]
assert len(variants) == 35
driver = (ROOT / 'scratchpad/c03-status-batch777.py').read_text(encoding='utf-8')
driver = driver.replace('777', '779').replace('775', '778').replace('BATTERY_ACTOR778', 'CLOCK_SCOPE778')
start = driver.index('# Retain every case')
end = driver.index('manifest =', start)
extension = """# All fifteen existing clock cases, in the same order, then35 development variants.
panel = [c for c in panel if c['group'] == 'clock']
assert len(panel) == 15
for index, text in enumerate(VARIANTS, 1):
    panel.append({'case_id': f'clock-variant779-{index:02d}', 'group': 'clock',
                  'origin': 'assistant development clock scope generalization', 'text': text,
                  'supports': [c['case_id'] for c in panel[:15] if c['case_id'].startswith('H')],
                  'criterion': panel[0]['criterion']})
assert len(panel) == 50 and len({c['case_id'] for c in panel}) == 50
""".replace('VARIANTS', repr(variants))
driver = driver[:start] + extension + driver[end:]
driver = driver.replace('Complete battery category plus ten development variants', 'Complete clock category plus35 development variants')
driver = driver.replace('Complete seven-case battery category plus ten declared development variants after battery actor778 candidate; original battery criterion unchanged.',
                        'Complete fifteen-case clock category plus35 declared development variants after shared clock scope778; original clock criterion unchanged.')
driver = driver.replace("'registered_turns': 17", "'registered_turns': 50")
target = ROOT / 'scratchpad/c03-status-batch779.py'
assert not target.exists()
target.write_bytes(driver.encode('utf-8'))
reviewer = (ROOT / 'scratchpad/c03-review-status777.py').read_text(encoding='utf-8')
reviewer = reviewer.replace('777', '779').replace('source775', 'source778').replace('len(panel) == 17', 'len(panel) == 50')
(ROOT / 'scratchpad/c03-review-status779.py').write_bytes(reviewer.encode('utf-8'))
write(OUT / 'PLAN.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'parent': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'evidence': ['STATUS_BATCH772/RESULT.json', 'tests/test_effect_intent.py:3210-3222,4322-4398',
                 'tests/test_c03_calendar_date.py'],
    'diagnosis': 'Three overlapping but inconsistent closed clock readers veto or omit actual local reads before inference.',
    'change': 'One whole-request clock grammar shared by direct selection, clause read selection and domain gate. Reuse request envelope; share its action heads with clause boundaries. Retain contextual nominal clock gate.',
    'baseline': '50 failures/30 passes in80 new controls; earlier collection failed because pytest reserves request as a parameter name, renamed utterance.',
    'initial_owners': '2051pass/6fail. Repaired definition/embedded question/legacy need-to-know/splitter regressions. Two prohibition fixtures lacked the prohibited operations needed by the existing disjoint-operation proof; supplied those catalog operations, no source negation change.',
    'boundary': '6pass/2036deselected,1.12s; full owners still required.',
    'pending': 'Owners/current integrity/Fast then50 product turns. No native model comparison, UI, voice or reserve credit.',
    'model_prompt_sampler_budget_changes': False,
    'coverage_added': 0, 'survey': {'covered': 26, 'open': 716, 'not_applicable': 0}})
note = ('778 candidato: tres puertas de reloj unificadas, envoltorios y fronteras de cláusula compartidos. '
        '80 controles nuevos; baseline50fail/30pass. Primera regresión2051pass/6fail; límites corregidos6pass. '
        'Pendientes dueñas completas/integridad/Fast y779 categoría completa15+35variantes. No fuente adoptada ni cobertura nueva;26/716/0.\n\n')
cp = BASE / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
pending.write_bytes(note.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(checkpoint=note.strip(), workStatus='clock_scope778_candidate_validation_pending',
             continuation='Finish current clock778 owner/integrity/Fast run, then frozen50 registered product779. Do not edit sealed sources during verification.')
write(BASE / 'RELEVO_ACTIVO.json', state)
print(json.dumps({'pins': len(paths), 'program': program['sha256'], 'product_turns': 50}))
