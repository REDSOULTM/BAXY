"""Seal the single scope projection change and run its Fast gate, without inference."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/PROCESS_SCOPE806'
private = Path('C:/Users/usuario/AppData/Local/BAXY/C03-process-scope806-private')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())


assert not out.exists() and not private.exists()
changed = {
    'src/baxy_mind/measurement_prose_projection.py',
    'tests/test_c03_process_projection_scope.py',
    'tests/test_c03_process_inventory.py',
    'tests/test_c03_process_scope_prompt.py',
}
baseline = root / 'artifacts/comprobaciones/C03/PROCESS_DEADLINE804'
old = read(baseline / 'SOURCE_PINS.json')
assert all(sha(root / p) == h for p, h in old.items() if p not in changed)
assert read(baseline / 'FULL_RETRY1/FULL_EXIT.json')['exit_code'] == 0
assert read(root / 'artifacts/comprobaciones/C03/PROCESS_BATCH805/ROOT_ADJUDICATION.json')['valid'] == 37
out.mkdir()
private.mkdir()
pins = {p: sha(root / p) for p in sorted(set(old) | changed)}
assert len(pins) == 29
write(out / 'SOURCE_PINS.json', pins)
for p in pins:
    target = private / 'source' / p
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / p, target)
write(out / 'CANDIDATE.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'candidate': 806, 'adopted': False,
    'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'changed_files': sorted(changed),
    'difference': 'Six lines in existing measurement projection describe the accessible observation boundary instead of copying its internal enum. Canonical observations, counts, rows, units, order, prompt, sampler, model, budgets and checker remain unchanged.',
    'cause': '805 memory_rank-08 repeats accessible_processes in all six attempts, gets internal_code vetoes and no response despite factual first draft. 805 root verdict37/50 preserved.',
    'owners': 'Root: six complete suites, 198 passed / 0 skipped in2.72s; tool exec35c6d3 exit0.',
    'baseline_full': 'PROCESS_DEADLINE804/FULL_RETRY1/FULL_EXIT.json covers previous Python802+C#804 only.806 is Python-only; new owner+Fast and product807 required. Final Full remains required.',
    'rows_proposal': 'Isolated, not integrated or measured in806.',
    'survey_counts': {'covered': 28, 'open': 714, 'not_applicable': 0},
})
write(out / 'OWNERS_PYTHON_EXIT.json', {
    'exit_code': 0, 'passed': 198, 'skipped': 0, 'seconds': 2.72,
    'command': 'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8 -m pytest tests/test_c03_process_projection_scope.py tests/test_c03_process_inventory.py tests/test_c03_process_scope_prompt.py tests/test_system_measurement_prose_projection.py tests/test_c03_observed_process_vocabulary.py tests/test_c03_process_output_budget.py -q',
    'evidence': 'Root tool command chunk35c6d3; complete stdout summary198 passed in2.72s.',
})
command = [shutil.which('pwsh'), '-NoProfile', '-File', 'scripts/test_source_quality.ps1', '-Mode', 'Fast']
assert command[0]
log = private / 'fast.log'
with log.open('wb') as stream:
    process = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL,
                               stdout=stream, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    write(out / 'VALIDATION_PROCESS.json', {'pid': process.pid, 'command': command, 'log': str(log)})
    print(json.dumps({'pid': process.pid, 'validation': 'Fast806', 'pins': len(pins)}), flush=True)
    code = process.wait()
unchanged = all(sha(root / p) == h for p, h in pins.items())
write(out / 'VALIDATION_EXIT.json', {'exit_code': code, 'source_pins_unchanged': unchanged,
    'source_pins_sha256': sha(out / 'SOURCE_PINS.json'), 'log_sha256': sha(log),
    'private_log': str(log), 'adopted': False})
print(json.dumps({'exit_code': code, 'source_pins_unchanged': unchanged}), flush=True)
raise SystemExit(code if unchanged else 2)
