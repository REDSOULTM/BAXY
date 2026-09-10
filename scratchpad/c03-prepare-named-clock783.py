"""Seal shared clock validation and prepare the identical50-value comparison."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'NAMED_CLOCK783'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not OUT.exists()
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
OUT.mkdir()
sys.path.insert(0, str(ROOT))
from scripts.wake_validation_program_tree import fingerprint_program_tree
prior = read(BASE / 'CLOCK_CONTEXT781/PROGRAM.json')
program = fingerprint_program_tree(repository_root=ROOT, source_roots=[ROOT / p for p in prior['roots']])
assert program['pythonFiles'] == 407
paths = ['src/baxy_mind/llm.py', 'tests/test_c03_named_clock.py', 'tests/test_c03_request_preservation.py',
         'experiments/stt_quality/evaluate_reserved_stt.py', 'experiments/stt_quality/audit_fresh_postweight_stt_sources.py',
         'tests/test_price_v8_veto_damage_by_cause.py', 'src/baxy_mind/__main__.py', 'src/baxy_mind/effect_intent.py']
for name in paths[3:5]:
    p = ROOT / name
    text = p.read_text(encoding='utf-8')
    assert text.count(prior['sha256']) == 1
    p.write_bytes(text.replace(prior['sha256'], program['sha256']).encode('utf-8'))
p = ROOT / paths[5]
text = p.read_text(encoding='utf-8')
old = hashlib.sha256(subprocess.check_output(['git', 'show', 'HEAD:src/baxy_mind/llm.py'])).hexdigest()
assert text.count(old) == 1
p.write_bytes(text.replace(old, sha(ROOT / paths[0])).encode('utf-8'))
write(OUT / 'SOURCE_PINS.json', {p: sha(ROOT / p) for p in paths})
write(OUT / 'PROGRAM.json', program)
for name in ['baseline', 'owners', 'fixed']:
    raw = (Path(os.environ['TEMP']) / f'c03-clock783-{name}.log').read_bytes()
    (OUT / (name + '.log')).write_bytes(('\n'.join(l.rstrip() for l in raw.decode('utf-8-sig').splitlines()) + '\n').encode())
driver = (ROOT / 'scratchpad/c03-clock-values780.py').read_text(encoding='utf-8')
driver = driver.replace('780', '784').replace('CLOCK_SCOPE778', 'NAMED_CLOCK783')
start = driver.index("assert b'2298 passed, 1 skipped'")
end = driver.index('manifest = ', start)
driver = driver[:start] + "validation = read(BASE / 'NAMED_CLOCK783/VALIDATION.json')\nassert validation['failed'] == 0 and validation['fast_exit_code'] == 0 and validation['terminal_collected']\n" + driver[end:]
start = driver.index("captured = read(PREVIOUS / 'review.json')")
end = driver.index('for key in list(os.environ):', start)
driver = driver[:start] + """OUT.mkdir()
PRIVATE.mkdir()
cases = copy.deepcopy(read(PRIVATE.parent / 'C03-clock-values780-private/cases.json'))
assert len(cases) == 50
write(PRIVATE / 'cases.json', cases)
""" + driver[end:]
driver = driver.replace('779 complete observed clock situation; only UTC, explicit offset and user request vary in declared synthetic fixtures.',
                        'Identical50 cases, IDs, observed values, questions and criteria from780; only validator source783 changed. Original situation came from779.')
p = ROOT / 'scratchpad/c03-clock-values784.py'
assert not p.exists()
p.write_bytes(driver.encode('utf-8'))
write(OUT / 'PLAN.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'parent': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'cause': '780-35 raw correct noon wording rejected by missing_name. Both clock gates recognized only numeric/spoken hour+minute.',
    'change': 'One clock value extractor and one fact check shared by both gates. Named exact noon/midnight use assertion frames and complete endings; all contradicting values retained, including12AM/PM.',
    'baseline': '39fail/34pass; first owner run7fail/404pass identified7 English visible fixtures with Spanish questions. Corrected fixture language only; no language veto relaxed.',
    'focused_fixed': '425pass/0skip/3.90s including voice clock projection;75new controls and two one-post composer stub replays.',
    'pending': 'Complete owner/integrity/Fast then identical50 fixture784 with local model and every raw response retained.',
    'unchanged': 'Model, backend, template, prompts, sampler, token budgets, context781, providers. No spelling filter.',
    'coverage_added': 0, 'survey': {'covered': 28, 'open': 714, 'not_applicable': 0}})
note = ('783 candidato: extractor compartido de valores de reloj reconoce mediodía/medianoche exactos y conserva contradicciones. '
        '425pass/0skip/3,90s;75controles nuevos. Dos stubs conservan borrador correcto con1post. '
        '8pins sellados; faltan dueñas completas/integridad/Fast y784 mismos50fixtures780. Modelo/prompt/receta intactos.28/714/0.\n\n')
p = BASE / 'CHECKPOINT.md'; p.write_bytes(note.encode('utf-8') + p.read_bytes())
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(checkpoint=note.strip(), workStatus='named_clock783_candidate', activeValidation=None,
             continuation='Run sealed783 owner/integrity/Fast, collect same session, then identical50 fixture784. No edits during runs.')
write(BASE / 'RELEVO_ACTIVO.json', state)
print(json.dumps({'pins': len(paths), 'program': program['sha256'], 'probe_cases': 50}))
