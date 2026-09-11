"""Seal the process-row instruction replacement; Fast gate only, no inference."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/PROCESS_ROWS808'
private = Path('C:/Users/usuario/AppData/Local/BAXY/C03-process-rows808-private')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())


assert not out.exists() and not private.exists()
changed = {'src/baxy_mind/llm.py', 'tests/test_c03_process_scope_prompt.py'}
old = read(root / 'artifacts/comprobaciones/C03/PROCESS_SCOPE806/SOURCE_PINS.json')
assert all(sha(root / p) == h for p, h in old.items() if p not in changed)
assert read(root / 'artifacts/comprobaciones/C03/PROCESS_BATCH807/ROOT_ADJUDICATION.json')['valid'] == 37
assert read(root / 'artifacts/comprobaciones/C03/PROCESS_BATCH807/EXIT.json')['exit_code'] == 0
out.mkdir()
private.mkdir()
pins = {p: sha(root / p) for p in sorted(old)}
assert len(pins) == 29
write(out / 'SOURCE_PINS.json', pins)
for p in pins:
    target = private / 'source' / p
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / p, target)
write(out / 'CANDIDATE.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'candidate': 808, 'adopted': False,
    'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'changed_files': sorted(changed),
    'difference': 'Replace existing process-inventory paragraph: narrate supplied selected rows once in original order, preserve name/PID/observed resource value/unit, actual narrated count and observed scope; count-only and process-vs-app distinction retained. No additional checker or prompt layer.',
    'root_review': 'Agent memory-only wording generalized to observed resource value/unit, tested on CPU and memory. Canonical evidence and scope806 projection remain unchanged. Existing top-one PID exception removed to meet memory criterion.',
    'cause': '80737/50: incomplete lists, missing memory PIDs and contradictory row counts remain. Scope806 recovered memory08 but produced5gains/5losses vs805; no adoption. All root judgments preserved.',
    'owners': 'Root six complete suites204 passed/0skipped/2.78s, tool chunkffb3ac exit0. Includes CPU and memory on first/retry seams; no inference.',
    'baseline_full': 'PROCESS_DEADLINE804/FULL_RETRY1/FULL_EXIT.json is previous Full804 only.808 is Python-only; owners+Fast then product809. Cumulative adoption and final Full remain required by goal.',
    'unchanged': 'Model, backend, sampler, budgets, factual checker, canonical observations, frozen50 panel.',
    'survey_counts': {'covered': 28, 'open': 714, 'not_applicable': 0},
})
write(out / 'OWNERS_PYTHON_EXIT.json', {
    'exit_code': 0, 'passed': 204, 'skipped': 0, 'seconds': 2.78,
    'command': 'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8 -m pytest tests/test_c03_process_scope_prompt.py tests/test_c03_process_inventory.py tests/test_c03_process_projection_scope.py tests/test_system_measurement_prose_projection.py tests/test_c03_observed_process_vocabulary.py tests/test_c03_process_output_budget.py -q',
    'evidence': 'Root tool command chunkffb3ac; complete stdout summary204 passed in2.78s.',
})
command = [shutil.which('pwsh'), '-NoProfile', '-File', 'scripts/test_source_quality.ps1', '-Mode', 'Fast']
assert command[0]
log = private / 'fast.log'
with log.open('wb') as stream:
    process = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL,
                               stdout=stream, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    write(out / 'VALIDATION_PROCESS.json', {'pid': process.pid, 'command': command, 'log': str(log)})
    print(json.dumps({'pid': process.pid, 'validation': 'Fast808', 'pins': len(pins)}), flush=True)
    code = process.wait()
unchanged = all(sha(root / p) == h for p, h in pins.items())
write(out / 'VALIDATION_EXIT.json', {'exit_code': code, 'source_pins_unchanged': unchanged,
    'source_pins_sha256': sha(out / 'SOURCE_PINS.json'), 'log_sha256': sha(log),
    'private_log': str(log), 'adopted': False})
print(json.dumps({'exit_code': code, 'source_pins_unchanged': unchanged}), flush=True)
raise SystemExit(code if unchanged else 2)
