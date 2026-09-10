"""Seal787 source and existing integrity declarations before final validation."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'INVENTORY_BUDGET787'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    assert not path.exists(), path
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not (OUT / 'SOURCE_PINS.json').exists()
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
paths = ['src/baxy_mind/llm.py', 'src/baxy_mind/window_prose_facts.py',
         'tests/test_c03_inventory_output_budget.py', 'tests/test_c03_inventory_scope_polarity.py',
         'tests/data/c03_inventory_completion786.json',
         'experiments/stt_quality/evaluate_reserved_stt.py', 'experiments/stt_quality/audit_fresh_postweight_stt_sources.py',
         'tests/test_price_v8_veto_damage_by_cause.py', 'src/baxy_mind/__main__.py', 'src/baxy_mind/effect_intent.py']
for name in paths:
    p = ROOT / name
    raw = p.read_bytes()
    if b'\r\n' in raw:
        p.write_bytes(raw.replace(b'\r\n', b'\n'))
sys.path.insert(0, str(ROOT))
from scripts.wake_validation_program_tree import fingerprint_program_tree
prior = read(BASE / 'NAMED_CLOCK783/PROGRAM.json')
program = fingerprint_program_tree(repository_root=ROOT, source_roots=[ROOT / p for p in prior['roots']])
assert program['pythonFiles'] == 407
for name in paths[5:7]:
    p = ROOT / name
    content = p.read_text(encoding='utf-8')
    assert content.count(prior['sha256']) == 1
    p.write_bytes(content.replace(prior['sha256'], program['sha256']).encode('utf-8'))
p = ROOT / paths[7]
old_llm = hashlib.sha256(subprocess.check_output(['git', 'show', 'HEAD:src/baxy_mind/llm.py'])).hexdigest()
content = p.read_text(encoding='utf-8')
assert content.count(old_llm) == 1
p.write_bytes(content.replace(old_llm, sha(ROOT / paths[0])).encode('utf-8'))
write(OUT / 'PROGRAM.json', program)
write(OUT / 'SOURCE_PINS.json', {p: sha(ROOT / p) for p in paths})
for name in ['scope-first', 'scope-second', 'owners', 'owners-fixed']:
    p = Path(os.environ['TEMP']) / f'c03-inventory-budget787-{name}.log'
    (OUT / (name + '.log')).write_bytes(p.read_bytes().replace(b'\r\n', b'\n'))
assert b'1681 passed, 121 subtests passed in 8.58s' in (OUT / 'owners-fixed.log').read_bytes()
write(OUT / 'PLAN.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'cause': '786: six correct512 completions versus six256 cuts; first composer replay exposed five false scope/quantity vetoes.',
    'changes': ['Reuse existing512 cap only for dense verified inventory; original messages/sampler unchanged.',
                'Replace clause-wide numeric context with per-quantity binding; observed-qualified denominator is not an unknown global total; two correct page/inventory quantities disclose a subset.'],
    'controls': 118, 'focused': {'passed': 1681, 'subtests_passed': 121, 'failed': 0, 'skipped': 0},
    'root_review': 'Six recorded full answers now delivered exactly in one stub each with original786 messages; false counts, unknown global totals and undisclosed subsets remain rejected.',
    'source_kind': 'Python only; C#764 timeout unchanged. No Full needed until combined source or final closure.',
    'pending': 'Sealed owners/integrity/Fast then real full composer50 cases with raw requests and retry records. No survey credit yet.'})
note = '787 candidato sellado:118controles nuevos,1681pass+121subtests/0skip/8,58s;seis finales786seentregan1stub con mensajesidénticos. Reusa512en inventario denso y repara ligadura cantidad/alcance sin nuevas instrucciones.10pins/programa407 sellados. Faltan owners/integridad/Fast finales y788compositorreal50casos. Sin fuente adoptada,28/714/0.'
r = read(BASE / 'RELEVO_ACTIVO.json')
r.update(checkpoint=note, workStatus='inventory_budget787_sealed_validation_pending', activeValidation=None,
         continuation='Run sealed787 owners/integrity/Fast; no edits. If green, run real50 composer788 under registered command. All raw and final answers require adjudication.')
(BASE / 'RELEVO_ACTIVO.json').write_bytes((json.dumps(r, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
cp = BASE / 'CHECKPOINT.md'
cp.write_bytes((note + '\n\n').encode('utf-8') + cp.read_bytes())
print(json.dumps({'source_pins': len(paths), 'program': program['sha256']}))
