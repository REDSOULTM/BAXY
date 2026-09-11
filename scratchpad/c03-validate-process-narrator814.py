"""Seal removal of the redundant per-reply cardinality obligation; Fast only."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/PROCESS_NARRATOR814'
private = Path('C:/Users/usuario/AppData/Local/BAXY/C03-process-narrator814-private')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())


assert root == Path('D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO')
assert not out.exists() and not private.exists()
changed = {'src/baxy_mind/llm.py', 'tests/test_c03_process_scope_prompt.py'}
old = read(root / 'artifacts/comprobaciones/C03/PROCESS_COUNTS812/SOURCE_PINS.json')
assert all(sha(root / p) == h for p, h in old.items() if p not in changed)
assert read(root / 'artifacts/comprobaciones/C03/PROCESS_BATCH813/ROOT_ADJUDICATION.json')['valid'] == 39
assert read(root / 'artifacts/comprobaciones/C03/PROCESS_BATCH813/EXIT.json')['exit_code'] == 0
out.mkdir()
private.mkdir()
pins = {p: sha(root / p) for p in sorted(set(old) | changed)}
assert len(pins) == 31
write(out / 'SOURCE_PINS.json', pins)
for p in pins:
    target = private / 'source' / p
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / p, target)
write(out / 'CANDIDATE.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'candidate':814, 'adopted':False,
    'base_commit':subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'changed_files':sorted(changed),
    'difference':'Remove only the obligation to recite both counts on every list/ranking reply. Count-only instruction, subset disclosure, selected rows and all projected facts remain unchanged. No new layer, verifier or output template.',
    'root_review':'Exact two-file diff: one prompt clause removed and its obsolete string assertion removed. All count, scope, identity, row-order and first/retry behavior tests retained, including direct valid count replies in both languages. Data812 unchanged.',
    'cause':'81339/50 vs81140: six false displayed cardinalities, two observed-versus-returned confusions, internal field leak, exhausted terminal and app aggregation failure. Obliging both counts in every reply remains a hypothesis; no improvement claimed before815.',
    'owners':'Root eight complete suites306 passed/0skipped/3.62s; command chunke7207b exit0. Includes direct valid count replies and retry ES/EN, preserving the no-extra-call check.',
    'baseline_full':'Full804/FULL_RETRY1 is previous baseline only, not Full814. Python-only814 owners+Fast precede815; cumulative adoption and final Full remain required.',
    'unchanged':'Model, backend, sampler, budgets, factual checker, count representation812, identities810, canonical observations, frozen50 panel.',
    'survey_counts':{'covered':28,'open':714,'not_applicable':0},
})
write(out / 'OWNERS_PYTHON_EXIT.json', {
    'exit_code':0,'passed':306,'skipped':0,'seconds':3.62,
    'command':'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8 -m pytest tests/test_c03_process_projection_scope.py tests/test_c03_process_inventory.py tests/test_c03_process_scope_prompt.py tests/test_c03_process_identity_projection.py tests/test_c03_process_output_budget.py tests/test_system_measurement_prose_projection.py tests/test_c03_observed_process_vocabulary.py tests/test_c03_process_count_projection.py -q',
    'evidence':'Root command chunke7207b exit0:306 passed in3.62s.',
})
command = [shutil.which('pwsh'), '-NoProfile', '-File', 'scripts/test_source_quality.ps1', '-Mode', 'Fast']
assert command[0]
log = private / 'fast.log'
with log.open('wb') as stream:
    process = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL,
                               stdout=stream, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    write(out / 'VALIDATION_PROCESS.json', {'pid':process.pid,'command':command,'log':str(log)})
    print(json.dumps({'pid':process.pid,'validation':'Fast814','pins':len(pins)}), flush=True)
    code = process.wait()
unchanged = all(sha(root / p) == h for p, h in pins.items())
write(out / 'VALIDATION_EXIT.json', {'exit_code':code,'source_pins_unchanged':unchanged,
    'source_pins_sha256':sha(out / 'SOURCE_PINS.json'),'log_sha256':sha(log),
    'private_log':str(log),'adopted':False})
print(json.dumps({'exit_code':code,'source_pins_unchanged':unchanged}), flush=True)
raise SystemExit(code if unchanged else 2)
