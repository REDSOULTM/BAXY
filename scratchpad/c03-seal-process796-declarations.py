"""Advance current-source declarations; consumed historical evidence remains sealed."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/PROCESS_REPAIR796'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
initial = read(out / 'SOURCE_PINS.json')
assert len(initial) == 14 and all(sha(root / p) == h for p, h in initial.items())
assert read(out / 'FULL_INITIAL_ABORT.json')['status'] == 'aborted_not_passed'
prior = read(root / 'artifacts/comprobaciones/C03/INVENTORY_VETO793/PROGRAM.json')
prior_pins = read(root / 'artifacts/comprobaciones/C03/INVENTORY_VETO793/SOURCE_PINS.json')
sys.path.insert(0, str(root))
from scripts.wake_validation_program_tree import fingerprint_program_tree
program = fingerprint_program_tree(repository_root=root, source_roots=[root / p for p in prior['roots']])
assert program['pythonFiles'] == prior['pythonFiles'] == 407
extra = ['experiments/stt_quality/evaluate_reserved_stt.py',
         'experiments/stt_quality/audit_fresh_postweight_stt_sources.py',
         'tests/test_price_v8_veto_damage_by_cause.py']
private = Path(read(out / 'CANDIDATE.json')['private_snapshot'])
for name in extra[:2]:
    p = root / name
    text = p.read_text(encoding='utf-8-sig')
    assert text.count(prior['sha256']) == 1
    p.write_bytes(text.replace(prior['sha256'], program['sha256']).encode('utf-8'))
p = root / extra[2]
text = p.read_text(encoding='utf-8-sig')
for name in ['src/baxy_mind/__main__.py', 'src/baxy_mind/llm.py']:
    assert text.count(prior_pins[name]) == 1
    text = text.replace(prior_pins[name], sha(root / name))
p.write_bytes(text.encode('utf-8'))
pins = dict(initial)
for name in extra:
    p = private / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((root / name).read_bytes())
    pins[name] = sha(root / name)
(out / 'SOURCE_PINS.initial.json').write_bytes((out / 'SOURCE_PINS.json').read_bytes())
(out / 'SOURCE_PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
(out / 'PROGRAM.json').write_text(json.dumps(program, indent=2) + '\n', encoding='utf-8')
(out / 'SOURCE_PATCH.diff').write_bytes(subprocess.check_output(['git', 'diff', '--binary', '--', *pins], cwd=root))
state = read(out / 'CANDIDATE.json')
state.update(source_paths=17, initial_behavior_pins_unchanged=True,
             declaration_update='Current program407 and replaced-program declarations now identify796. Historical STT/V8 corpora, receipts, verdicts and evidence unchanged. Initial Full intentionally aborted before anticipated known pin mismatch; complete rerun required.')
(out / 'CANDIDATE.json').write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'source_pins': len(pins), 'program': program, 'behavior_unchanged': True}))
