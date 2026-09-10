"""Seal the inventory correction candidate and its current evidence declarations."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'INVENTORY_CORRECTION768'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not OUT.exists()
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
OUT.mkdir()
paths = ['src/baxy_mind/llm.py', 'src/baxy_mind/window_prose_facts.py',
    'tests/test_c03_inventory_semantic_projection.py', 'tests/test_c03_window_state_facts.py',
    'experiments/stt_quality/evaluate_reserved_stt.py',
    'experiments/stt_quality/audit_fresh_postweight_stt_sources.py',
    'tests/test_price_v8_veto_damage_by_cause.py']
# Pin canonical bytes before validation, never after a product run.
for relative in paths:
    path = ROOT / relative
    path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
sys.path.insert(0, str(ROOT))
from scripts.wake_validation_program_tree import fingerprint_program_tree
prior = read(BASE / 'TRUNCATION766/PROGRAM.json')
program = fingerprint_program_tree(repository_root=ROOT, source_roots=[ROOT / p for p in prior['roots']])
assert program['pythonFiles'] == 407
for relative in paths[4:6]:
    path = ROOT / relative
    data = path.read_text(encoding='utf-8')
    assert data.count(prior['sha256']) == 1
    path.write_bytes(data.replace(prior['sha256'], program['sha256']).encode('utf-8'))
old_llm = read(BASE / 'TRUNCATION766/SOURCE_PINS.json')[paths[0]]
v8 = ROOT / paths[-1]
data = v8.read_text(encoding='utf-8')
assert data.count(old_llm) == 1
v8.write_bytes(data.replace(old_llm, sha(ROOT / paths[0])).encode('utf-8'))
write(OUT / 'PROGRAM.json', program)
write(OUT / 'SOURCE_PINS.json', {p: sha(ROOT / p) for p in paths})
write(OUT / 'PLAN.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'source_parent': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'cause': '767 H0023 unobserved chronology is correctly rejected but its cause is dropped; retry forces20-window inventory into one sentence.',
    'change': 'Existing window factual feedback now carries unsupported chronology; inventory retries preserve requested list/page scope. No model condition, names, new response template, deadline or sampler change.',
    'first_attempt_unchanged': True, 'factual_acceptance_rules_unchanged': True,
    'tests': '24 new ES/EN×2 model paths×3 page sizes×2/3 attempts; existing chronology/uncertainty checks strengthened.775owners pass before canonical-byte preparation.',
    'initial_test_error': '24 initial failures compared full first/retry user messages despite existing movement of the language instruction to system. Corrected assertion compares request and decoded facts; full replies and rejection assertions unchanged.',
    'validation_pending': 'Owners on sealed bytes, complete window suites, current-pin integrity, Fast. Publish after green, then registered73 regression.',
    'coverage_added': 0, 'survey': {'covered': 26, 'open': 716, 'not_applicable': 0}})
for stem in ['owners', 'owners-initial']:
    (OUT / (stem + '-before-seal.log')).write_bytes((Path(os.environ['TEMP']) /
        ('c03-inventory-correction768-' + stem + '.log')).read_bytes().replace(b'\r\n', b'\n'))
runner = (ROOT / 'scratchpad/c03-status-batch767.py').read_text(encoding='utf-8')
runner = runner.replace('STATUS_BATCH767', 'STATUS_BATCH769').replace('batch767', 'batch769').replace('profile767', 'profile769')
runner = runner.replace('TRUNCATION766', 'INVENTORY_CORRECTION768').replace('pins766', 'pins768').replace('source766', 'source768')
runner = runner.replace('after truncation766 with dense764', 'after inventory correction768 with dense764')
runner = runner.replace('Published766 owners/current pin integrity and Fast', 'Published768 owners/current pin integrity and Fast')
target = ROOT / 'scratchpad/c03-status-batch769.py'
assert not target.exists()
target.write_bytes(runner.encode('utf-8'))
reviewer = (ROOT / 'scratchpad/c03-review-status767.py').read_text(encoding='utf-8')
reviewer = reviewer.replace('767', '769').replace('source766_unchanged', 'source768_unchanged')
target = ROOT / 'scratchpad/c03-review-status769.py'
assert not target.exists()
target.write_bytes(reviewer.encode('utf-8'))
cp = BASE / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
note = ('768 candidato: canal factual existente conserva causa de cronología no observada; reintentos de inventario permiten lista completa. '
    '775owners antes de sello,24nuevos; primer fallo de aserto sobre posición de idioma conservado, solicitud/hechos se comparan decodificados. '
    'Fuente/declaraciones7 pins congelados, faltan owners/integridad/Fast sobre esos bytes.769 preparado, no ejecutar hasta validar/publicar. '
    'No proceso de inferencia activo. Encuesta26/716/0.\n\n')
pending.write_bytes(note.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
r = read(BASE / 'RELEVO_ACTIVO.json')
r.update(checkpoint=note.strip(), activeValidation=None, workStatus='inventory_correction768_validation_pending',
    continuation='Validate sealed768 owners/window/integrity and Fast; publish then registered73 driver769.')
write(BASE / 'RELEVO_ACTIVO.json', r)
print(json.dumps({'source_pins': len(paths), 'program': program, 'driver769_prepared': True}))
