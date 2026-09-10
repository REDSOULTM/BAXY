"""Pin the candidate and update current declarations, never historical seals."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.wake_validation_program_tree import fingerprint_program_tree

BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'SEMANTIC_INVENTORY760'
assert not OUT.exists() or not any(OUT.iterdir())
OUT.mkdir(exist_ok=True)
source_paths = [
    'src/baxy_mind/llm.py', 'src/baxy_mind/window_prose_facts.py',
    'tests/test_c03_inventory_semantic_projection.py',
    'experiments/stt_quality/evaluate_reserved_stt.py',
    'experiments/stt_quality/audit_fresh_postweight_stt_sources.py',
    'tests/test_price_v8_veto_damage_by_cause.py',
]
for relative in source_paths:
    path = ROOT / relative
    path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
prior_program = json.loads((BASE / 'WINDOW_INVENTORY751/PROGRAM.json').read_text(encoding='utf-8-sig'))
program = fingerprint_program_tree(repository_root=ROOT, source_roots=[ROOT / relative for relative in prior_program['roots']])
assert program['pythonFiles'] == 407
old_program = '86dadf1b2b828862303f26908ca4f3d4c56315ab82aefe410dd549d2eab95111'
for relative in source_paths[3:5]:
    path = ROOT / relative
    text = path.read_text(encoding='utf-8')
    text, count = re.subn(
        r'(EXPECTED_PROGRAM_TREE_SHA256 = \(\s*")' + old_program + r'("\s*\))',
        lambda match: match[1] + program['sha256'] + match[2], text,
    )
    assert count == 1
    path.write_bytes(text.encode('utf-8'))
llm_hash = hashlib.sha256((ROOT / source_paths[0]).read_bytes()).hexdigest()
v8 = ROOT / source_paths[5]
text = v8.read_text(encoding='utf-8')
old_llm = '1ab5900c774df5fade2cb0724d27e7c4581f2c9686faf16ac7e05a7b91d234a8'
assert text.count(old_llm) == 1
v8.write_bytes(text.replace(old_llm, llm_hash).encode('utf-8'))


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


pins = {relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() for relative in source_paths}
write(OUT / 'SOURCE_PINS.json', pins)
write(OUT / 'PROGRAM.json', program)
write(OUT / 'PLAN.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'source_before': 'a4c95c61e507d9211d738ee1f5daf05cdb187230',
    'source_after_status': 'candidate_not_adopted', 'source_files': source_paths,
    'inherited_evidence': ['COMPOSE_BOUNDARY753', 'INVENTORY_PROJECTION757', 'INVENTORY_PROJECTION758', 'INVENTORY_PROJECTION759'],
    'changes': [
        'Preserve canonical inventory metadata; derive explicit page scope and unknown opening times from the typed verified result.',
        'Project only title/process identities for recognized identity/count requests; preserve all entries, duplicates and detailed observations for other requests.',
        'Reject unsupported chronological claims independently of model, preserving observed titles, page position and fresh-reading statements.',
    ],
    'historical_seals_unchanged': True, 'current_declarations_updated': source_paths[3:],
    'initial_checks': {'collection_error': 'pytest reserved parameter name request, corrected to user_text',
                       'preparation_error': 'Initially fingerprinted only src; assertion stopped before current declarations were written. Corrected to the same three roots as751 and both STT evaluators.',
                       'integrity_before_pins': '471passed/3failed/1environmental skip; expected current pins had not yet been updated after preparation failure',
                       'first_run': '274passed/5failed: folding discarded line breaks before identity masking',
                       'focused': '279passed', 'broad_owners': '4303passed/121subtests',
                       'final_window_owners': '950passed; added scope contrasts for fresh readings and unrelated uncertainty'},
    'next_validation': 'Current pin integrity + Fast; then source adoption/publication and registered73 category.',
    'survey_counts': {'covered': 26, 'open': 716, 'not_applicable': 0},
    'model_or_budget_changed': False, 'goal_complete': False,
})
for name in ['initial', 'initial2', 'focused', 'owners', 'final-owners']:
    source = Path(os.environ['TEMP']) / f'c03-inventory760-{name}.log'
    (OUT / f'{name}.log').write_bytes(source.read_bytes().replace(b'\r\n', b'\n'))
source = Path(os.environ['TEMP']) / 'c03-inventory760-integrity.log'
(OUT / 'integrity-before-pins.log').write_bytes(source.read_bytes().replace(b'\r\n', b'\n'))
checkpoint = ('760 fuente candidata: proyección explícita de página y fechas de apertura no observadas; conserva20/50identidades y detalles si se piden. '
              'Validador de recencia distingue identidad, posición de página y lectura fresca; no cambia modelo/prompt/presupuesto. '
              '950pruebas finales de ventana verdes;4303pass+121subtests previas con solapamiento. Primeras fallas conservadas. '
              'Programa407 actualizado y6fuentes selladas en SEMANTIC_INVENTORY760. Siguen integridad/Fast antes de adoptar/publicar; '
              'ninguna inferencia nueva ni cobertura.26/716/0.\n\n')
cp = BASE / 'CHECKPOINT.md'
cp.write_bytes(checkpoint.encode('utf-8') + cp.read_bytes())
relevo_path = BASE / 'RELEVO_ACTIVO.json'
relevo = json.loads(relevo_path.read_text(encoding='utf-8-sig'))
relevo.update(workStatus='semantic_inventory760_candidate_validation', checkpoint=checkpoint.strip(),
              previousGoalTurnClassification='progress',
              previousGoalTurnClassificationReason='Implemented the measured inventory projection and chronology validation with119new controls; owners green, final integrity and Fast pending.')
write(relevo_path, relevo)
print(json.dumps({'source_files': len(pins), 'program': program}))
