"""Seal the existing process identity projection; Fast only, no inference."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/PROCESS_IDENTITY810'
private = Path('C:/Users/usuario/AppData/Local/BAXY/C03-process-identity810-private')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())


assert root == Path('D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO')
assert not out.exists() and not private.exists()
changed = {'src/baxy_mind/measurement_prose_projection.py', 'tests/test_c03_process_inventory.py',
           'tests/test_c03_process_output_budget.py', 'tests/test_c03_process_projection_scope.py',
           'tests/test_c03_process_scope_prompt.py', 'tests/test_c03_process_identity_projection.py'}
old = read(root / 'artifacts/comprobaciones/C03/PROCESS_ROWS808/SOURCE_PINS.json')
assert all(sha(root / p) == h for p, h in old.items() if p not in changed)
assert read(root / 'artifacts/comprobaciones/C03/PROCESS_BATCH809/ROOT_ADJUDICATION.json')['valid'] == 37
assert read(root / 'artifacts/comprobaciones/C03/PROCESS_BATCH809/EXIT.json')['exit_code'] == 0
out.mkdir()
private.mkdir()
pins = {p: sha(root / p) for p in sorted(set(old) | changed)}
assert len(pins) == 30
write(out / 'SOURCE_PINS.json', pins)
for p in pins:
    target = private / 'source' / p
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / p, target)
write(out / 'CANDIDATE.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'candidate':810, 'adopted':False,
    'base_commit':subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'changed_files':sorted(changed),
    'difference':'Six lines in existing process measurement projection replace name and processId with one process_identity datum when both are valid. No new instruction, checker or layer.',
    'root_review':'Exact names and integer PIDs, including zero, preserved; incomplete or malformed identities remain typed. Canonical observations unchanged, as are row order, counts, scope and resource quantities/units. Owner expectations updated only at narrator projection seam.',
    'cause':'805,807,809 each37/50.809 has memory3/11 with omitted PIDs despite names/values. Change data representation after two instruction attempts without net improvement. Hypothesis is not an adoption.',
    'owners':'Root seven complete suites247 passed/0skipped/3.04s; command chunk44d93e exit0.',
    'baseline_full':'PROCESS_DEADLINE804/FULL_RETRY1/FULL_EXIT.json is previous Full804 only.810 is Python-only; owners+Fast precede811. Cumulative adoption and final Full remain required.',
    'unchanged':'Model, backend, sampler, prompts, budgets, factual checker, canonical observations, frozen50 panel.',
    'survey_counts':{'covered':28,'open':714,'not_applicable':0},
})
write(out / 'OWNERS_PYTHON_EXIT.json', {
    'exit_code':0,'passed':247,'skipped':0,'seconds':3.04,
    'command':'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8 -m pytest tests/test_c03_process_projection_scope.py tests/test_c03_process_inventory.py tests/test_c03_process_scope_prompt.py tests/test_system_measurement_prose_projection.py tests/test_c03_observed_process_vocabulary.py tests/test_c03_process_output_budget.py tests/test_c03_process_identity_projection.py -q',
    'evidence':'Root command chunk44d93e exit0:247 passed in3.04s.',
})
command = [shutil.which('pwsh'), '-NoProfile', '-File', 'scripts/test_source_quality.ps1', '-Mode', 'Fast']
assert command[0]
log = private / 'fast.log'
with log.open('wb') as stream:
    process = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL,
                               stdout=stream, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    write(out / 'VALIDATION_PROCESS.json', {'pid':process.pid,'command':command,'log':str(log)})
    print(json.dumps({'pid':process.pid,'validation':'Fast810','pins':len(pins)}), flush=True)
    code = process.wait()
unchanged = all(sha(root / p) == h for p, h in pins.items())
write(out / 'VALIDATION_EXIT.json', {'exit_code':code,'source_pins_unchanged':unchanged,
    'source_pins_sha256':sha(out / 'SOURCE_PINS.json'),'log_sha256':sha(log),
    'private_log':str(log),'adopted':False})
print(json.dumps({'exit_code':code,'source_pins_unchanged':unchanged}), flush=True)
raise SystemExit(code if unchanged else 2)
