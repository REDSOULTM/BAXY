"""Seal Python-only narrator821; run current Python/reference owners and Fast.
Full818/FULL_RETRY1 is inherited baseline evidence, never Full821.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess

import psutil

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/PROCESS_NARRATOR821'
private = Path('C:/Users/usuario/AppData/Local/BAXY/C03-process-narrator821-private')
baseline = root / 'artifacts/comprobaciones/C03/PROCESS_REPAIRS818/FULL_RETRY1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    assert not path.exists(), path
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert Path(__file__).resolve().parent.name == 'scratchpad'
assert root == Path('D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO')
assert (root / 'Baxy.slnx').is_file() and (root / 'main.py').is_file()
assert not private.exists()
assert not out.exists() or {p.name for p in out.iterdir()} == {
    'IDENTITY_REPAIR.json', 'WORKTREE_CHECK.json', 'WORKTREE_RELEASE.json', 'PROPOSAL.json',
}, 'Only root preparation metadata may precede the first validation'
changed = {
    'src/baxy_mind/llm.py',
    'tests/test_c03_process_scope_prompt.py',
    'tests/test_price_v8_veto_damage_by_cause.py',
    'experiments/stt_quality/evaluate_reserved_stt.py',
    'experiments/stt_quality/audit_fresh_postweight_stt_sources.py',
}
old = read(baseline / 'SOURCE_PINS.json')
assert len(old) == 33 and changed <= set(old)
assert all(sha(root / p) == h for p, h in old.items() if p not in changed)
full = read(baseline / 'FULL_EXIT.json')
assert full['exit_code'] == 0 and full['source_pins_unchanged'] is True
assert full['source_pins_sha256'] == sha(baseline / 'SOURCE_PINS.json')
assert read(baseline / 'OWNERS_DOTNET_EXIT.json')['exit_code'] == 0
assert read(root / 'artifacts/comprobaciones/C03/PROCESS_BATCH819/ROOT_ADJUDICATION.json')['valid'] == 40
assert read(root / 'artifacts/comprobaciones/C03/PROCESS_BATCH819/EXIT.json')['exit_code'] == 0
busy = [p.info for p in psutil.process_iter(['name', 'pid', 'cmdline'])
        if (p.info['name'] or '').lower() in {'llama-server.exe', 'baxy.exe', 'baxy-core.exe', 'testhost.exe'}
        or any('pytest' in part for part in p.info['cmdline'] or [])]
assert not busy, busy
out.mkdir(exist_ok=True)
private.mkdir()
pins = {p: sha(root / p) for p in sorted(old)}
assert len(pins) == 33
write(out / 'SOURCE_PINS.json', pins)
for p in pins:
    target = private / 'source' / p
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / p, target)
write(out / 'CANDIDATE.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'candidate': 821, 'adopted': False,
    'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'changed_files': sorted(changed),
    'difference': 'One process prompt clause asks to report observedProcessCount; two owner assertions cover it. Three current reference identities updated by root. No data, budgets, model, backend, panel or rubric changes.',
    'baseline': '819:40/50;801:35/50. No regrading or survey credit.',
    'measurement_plan': '822 repeats the frozen panel795/50 after current Python/reference owners and Fast pass.',
    'full_baseline': 'Python-only821 inherits Full818/FULL_RETRY1 and baseline .NET owners explicitly; this is not Full821, and baseline source hashes need not equal current candidate hashes. Adoption and final Full remain governed by the goal.',
    'baseline_source_pins_path': str(baseline / 'SOURCE_PINS.json'),
    'baseline_source_pins_sha256': sha(baseline / 'SOURCE_PINS.json'),
    'baseline_full_path': str(baseline / 'FULL_EXIT.json'),
    'baseline_full_sha256': sha(baseline / 'FULL_EXIT.json'),
    'baseline_owners_dotnet_path': str(baseline / 'OWNERS_DOTNET_EXIT.json'),
    'baseline_owners_dotnet_sha256': sha(baseline / 'OWNERS_DOTNET_EXIT.json'),
    'source_pins_sha256': sha(out / 'SOURCE_PINS.json'),
    'runner_sha256': sha(Path(__file__)),
    'survey_counts': {'covered': 28, 'open': 714, 'not_applicable': 0},
})
python = 'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe'
owners = [
    'tests/test_c03_process_scope_vocabulary.py', 'tests/test_compose_contract.py',
    'tests/test_c03_request_preservation.py', 'tests/test_c03_process_projection_scope.py',
    'tests/test_c03_process_inventory.py', 'tests/test_c03_process_scope_prompt.py',
    'tests/test_c03_process_identity_projection.py', 'tests/test_c03_process_output_budget.py',
    'tests/test_system_measurement_prose_projection.py',
    'tests/test_c03_observed_process_vocabulary.py', 'tests/test_c03_process_count_projection.py',
]
references = ['tests/test_price_v8_veto_damage_by_cause.py', 'tests/test_stt_quality_evaluators.py']
commands = [
    ('OWNERS_PYTHON', [python, '-X', 'utf8', '-m', 'pytest', '-q', *owners]),
    ('OWNERS_REFERENCE', [python, '-X', 'utf8', '-m', 'pytest', '-q', *references]),
    ('VALIDATION', [shutil.which('pwsh'), '-NoProfile', '-File', 'scripts/test_source_quality.ps1', '-Mode', 'Fast']),
]
for prefix, command in commands:
    assert command[0]
    log_path = private / (prefix.lower() + '.log')
    with log_path.open('wb') as stream:
        process = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        write(out / (prefix + '_PROCESS.json'), {
            'utc': datetime.now(timezone.utc).isoformat(), 'pid': process.pid,
            'command': command, 'private_log': str(log_path),
            'source_pins_sha256': sha(out / 'SOURCE_PINS.json'), 'runner_sha256': sha(Path(__file__)),
        })
        print(json.dumps({'validation': prefix, 'pid': process.pid, 'pins': len(pins)}), flush=True)
        code = process.wait()
    unchanged = all(sha(root / p) == h for p, h in pins.items())
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'exit_code': code,
              'command': command, 'source_pins_unchanged': unchanged,
              'source_pins_sha256': sha(out / 'SOURCE_PINS.json'),
              'log_sha256': sha(log_path), 'private_log': str(log_path), 'adopted': False}
    if prefix.startswith('OWNERS_'):
        log_text = log_path.read_text(encoding='utf-8-sig', errors='replace')
        summaries = [line for line in log_text.splitlines() if re.search(r'\d+ passed', line)]
        summary = summaries[-1] if summaries else ''
        result.update(passed=int(re.search(r'(\d+) passed', summary)[1]) if summary else 0,
                      skipped=int(m[1]) if (m := re.search(r'(\d+) skipped', summary)) else 0,
                      pytest_summary=summary,
                      expected_previous={'passed': 696, 'skipped': 0} if prefix == 'OWNERS_PYTHON'
                      else {'passed': 17, 'skipped': 1},
                      skip_accounting='Skips are environmental omissions, never counted as passes; inspect the saved log.')
    write(out / (prefix + '_EXIT.json'), result)
    print(json.dumps({'validation': prefix, **result}), flush=True)
    if code or not unchanged:
        raise SystemExit(code if code else 2)
    if prefix.startswith('OWNERS_'):
        assert result['passed'] > 0, 'No successful pytest summary found'
        if prefix == 'OWNERS_PYTHON':
            assert result['skipped'] == 0, 'Unexpected owner omission'
