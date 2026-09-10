"""Seal input-scope repair and prepare a complete battery-category regression."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'MACHINE_SCOPE773'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not OUT.exists()
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
OUT.mkdir()
sys.path.insert(0, str(ROOT))
from scripts.wake_validation_program_tree import fingerprint_program_tree
previous = read(BASE / 'INVENTORY_SCOPE771/PROGRAM.json')
program = fingerprint_program_tree(repository_root=ROOT, source_roots=[ROOT / p for p in previous['roots']])
assert program['pythonFiles'] == 407
declarations = ['experiments/stt_quality/evaluate_reserved_stt.py',
                'experiments/stt_quality/audit_fresh_postweight_stt_sources.py']
for name in declarations:
    path = ROOT / name
    text = path.read_text(encoding='utf-8')
    assert text.count(previous['sha256']) == 1
    path.write_bytes(text.replace(previous['sha256'], program['sha256']).encode('utf-8'))
paths = ['src/baxy_mind/effect_intent.py', 'tests/test_c03_machine_preposition_scope.py',
         *declarations, 'src/baxy_mind/llm.py', 'src/baxy_mind/window_prose_facts.py']
assert all(b'\r\n' not in (ROOT / p).read_bytes() for p in paths)
write(OUT / 'SOURCE_PINS.json', {p: sha(ROOT / p) for p in paths})
write(OUT / 'PROGRAM.json', program)
for name in ['baseline', 'owners', 'boundary']:
    raw = (Path(os.environ['TEMP']) / f'c03-machine-scope773-{name}.log').read_bytes()
    (OUT / (name + '-initial.log')).write_bytes(raw.replace(b'\r\n', b'\n'))
texts = [
    'Dime cuánta batería le queda a mi laptop.',
    'Baxy, comprueba cuánta batería le queda a esta computadora.',
    '¿Cuánta batería le queda a este PC?',
    'Dime cuánta batería le queda a mi notebook.',
    '¿Cuánta batería le queda a la laptop?',
    'Comprueba cuánta batería le queda a mi computadora.',
    'Baxy, dime cuánta battery le queda a mi laptop.',
    'How much battery is left?',
    'Check the battery level, please.',
    'Baxy, battery level please.',
]
extension = '''
# Retain every case and criterion of the complete battery category; the other
# categories were adjudicated in772. Added forms are development, not reserve.
panel = [c for c in panel if c['group'] == 'battery']
assert len(panel) == 7
for index, text in enumerate(EXTRA_TEXTS, 1):
    panel.append({'case_id': f'battery-variant774-{index:02d}', 'group': 'battery',
                  'origin': 'assistant development input-scope generalization', 'text': text,
                  'supports': ['H0037', 'H0144', 'H0359', 'H0379', 'H0665'],
                  'criterion': panel[0]['criterion']})
assert len(panel) == 17 and len({c['case_id'] for c in panel}) == 17
'''.replace('EXTRA_TEXTS', repr(texts))
driver = (ROOT / 'scratchpad/c03-status-batch772.py').read_text(encoding='utf-8')
driver = driver.replace('772', '774').replace('INVENTORY_SCOPE771', 'MACHINE_SCOPE773')
driver = driver.replace('pins771', 'pins773').replace('source771', 'source773')
driver = driver.replace('Frozen 73-case status regression', 'Complete battery category plus ten development variants')
anchor = "assert len(panel) == 73 and len({c['case_id'] for c in panel}) == 73\n"
assert driver.count(anchor) == 1
driver = driver.replace(anchor, anchor + extension)
driver = driver.replace("(PRIVATE / 'panel.json').write_bytes(panel_path.read_bytes())", "write(PRIVATE / 'panel.json', panel)")
driver = driver.replace("'panel_sha256': sha(panel_path)", "'parent_panel_sha256': sha(panel_path), 'panel_sha256': sha(PRIVATE / 'panel.json')")
driver = driver.replace('Registered73 product regression after inventory scope and correction771 with dense764; original panel/criteria.',
    'Complete seven-case battery category plus ten declared development variants after input-scope773; original battery criterion unchanged.')
driver = driver.replace('Published771', 'Published773').replace("'registered_turns': 73", "'registered_turns': 17")
target = ROOT / 'scratchpad/c03-status-batch774.py'
assert not target.exists()
target.write_bytes(driver.encode('utf-8'))
reviewer = (ROOT / 'scratchpad/c03-review-status772.py').read_text(encoding='utf-8')
reviewer = reviewer.replace('772', '774').replace('source771', 'source773').replace('len(panel) == 73', 'len(panel) == 17')
target = ROOT / 'scratchpad/c03-review-status774.py'
assert not target.exists()
target.write_bytes(reviewer.encode('utf-8'))
write(OUT / 'PLAN.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'parent': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'evidence': ['STATUS_BATCH772/RESULT.json H0359', 'test_effect_intent.py:4114-4248',
                 'REGISTRO_DE_MANTENIBILIDAD.md:1098-1124'],
    'diagnosis': 'Spanish a+determiner was treated as English indefinite foreign hardware, preventing a fresh battery read.',
    'change': 'Disambiguate existing indefinite-hardware rule; preserve exclusion of conditional remaining-state verbs and explicit other owner exposed by boundary tests.',
    'first_baseline': {'failed': 30, 'passed': 22, 'seconds': 0.93},
    'first_owner_run': {'failed': 2, 'passed': 2094, 'seconds': 57.35,
        'cause': 'Removing accidental indefinite-article veto exposed missing conditional quedar and explicit other-person scope boundaries; preserved and repaired.'},
    'boundary_final_before_seal': {'passed': 55, 'failed': 0, 'skipped': 0, 'seconds': 1.20},
    'next': 'Run sealed owners/current integrity/Fast, publish source, then registered774 complete battery category and10 development variants.',
    'unchanged': ['model', 'backend', 'sampler', 'prompts', 'budgets', 'Core and providers', 'V8 declarations', 'historical wake seals'],
    'coverage_added': 0, 'survey': {'covered': 26, 'open': 716, 'not_applicable': 0}})
note = ('773 candidato: preposición a+determinante deja de vetar lectura local; condicional quedar y dueño ajeno explícito conservan límites. '
        'Baseline30fail/22pass; primer2094pass/2fallos de frontera reparados,55controles finales pass. '
        'Programa407 y6pins sellados. Faltan owners/integridad/Fast y publicación;774 preparado con categoría batería7+10variantes. No inferencia activa,26/716/0.\n\n')
cp = BASE / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
pending.write_bytes(note.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(checkpoint=note.strip(), activeValidation=None, workStatus='machine_scope773_validation_pending',
             continuation='Validate sealed773 owners/current integrity/Fast; publish and run complete battery category774. No inference active.')
write(BASE / 'RELEVO_ACTIVO.json', state)
print(json.dumps({'source_pins': len(paths), 'program': program, 'prepared774_cases': 17}))
