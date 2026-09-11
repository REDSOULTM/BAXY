"""Seal the three isolated process repairs and run cumulative Fast then Full."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

import psutil

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/PROCESS_REPAIRS818'
private = Path('C:/Users/usuario/AppData/Local/BAXY/C03-process-repairs818-private')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    assert not path.exists(), path
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())


assert root == Path('D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO')
assert not out.exists() and not private.exists()
changed = {
    'src/Baxy.App/UserMessagePolicy.cs',
    'tests/Baxy.Integration.Tests/C03NaturalContextPhraseTests.cs',
    'src/baxy_mind/llm.py',
    'tests/test_c03_process_scope_vocabulary.py',
    'src/Baxy.App/MindSidecarClient.cs',
    'tests/Baxy.Integration.Tests/PlannerAppBoundaryTests.cs',
}
old = read(root / 'artifacts/comprobaciones/C03/PROCESS_NARRATOR814/SOURCE_PINS.json')
assert all(sha(root / p) == h for p, h in old.items() if p not in changed)
assert read(root / 'artifacts/comprobaciones/C03/PROCESS_BATCH815/ROOT_ADJUDICATION.json')['valid'] == 39
assert read(root / 'artifacts/comprobaciones/C03/PROCESS_BATCH815/EXIT.json')['exit_code'] == 0
busy = [p.info for p in psutil.process_iter(['name', 'pid', 'cmdline'])
        if (p.info['name'] or '').lower() in {'llama-server.exe', 'baxy.exe', 'baxy-core.exe', 'testhost.exe'}
        or any('pytest' in part for part in p.info['cmdline'] or [])]
assert not busy, busy
out.mkdir()
private.mkdir()
pins = {p: sha(root / p) for p in sorted(set(old) | changed)}
assert len(pins) == 33
write(out / 'SOURCE_PINS.json', pins)
for p in pins:
    target = private / 'source' / p
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / p, target)
write(out / 'CANDIDATE.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'candidate': 818, 'adopted': False,
    'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'changed_files': sorted(changed),
    'components': {
        '816': 'Remove the single current context substring from the internal-code blacklist. Natural bounded counts pass; actual internal codes remain rejected.',
        '817': 'Exclude observationScope and unit narrator metadata from the existing literal-word truncation vocabulary. Observed names, titles and capabilities remain protected. No dictionary exceptions or new checker.',
        '818': 'Select the existing dense composition budget for verified successful process observations with more than one returned row. Existing numeric budgets, token limits and retry counts remain unchanged.',
    },
    'root_review': 'Three independently diagnosed boundaries integrated one at a time with owner tests. No prompt or fact projection change; inherited 814 is not declared a successful category solution.',
    'baseline': '815:39/50, preserved; no panel regrading. Captured false-veto replay does not make its omitted observed population valid.',
    'native_isolation_limit': '815 t31 shows six result-composition attempts using outer5s/inner4s without a result draft. It does not measure isolated native completion duration.',
    'measurement_plan': '819 repeats the frozen50 after both gates. Overall recovery belongs to the combined repair; individual causal claims rely only on isolated owner reproductions.',
    'unchanged': 'Qwen model, backend, profile, sampler, prompts, projection812/810, canonical observations, panel795 and rubric; no new response layer.',
    'survey_counts': {'covered': 28, 'open': 714, 'not_applicable': 0},
})
write(out / 'OWNERS_PYTHON_EXIT.json', {
    'exit_code': 0, 'passed': 696, 'skipped': 0, 'seconds': 7.54,
    'command': 'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8 -m pytest -q tests/test_c03_process_scope_vocabulary.py tests/test_compose_contract.py tests/test_c03_request_preservation.py tests/test_c03_process_projection_scope.py tests/test_c03_process_inventory.py tests/test_c03_process_scope_prompt.py tests/test_c03_process_identity_projection.py tests/test_c03_process_output_budget.py tests/test_system_measurement_prose_projection.py tests/test_c03_observed_process_vocabulary.py tests/test_c03_process_count_projection.py',
    'evidence': 'Root command chunk ba1fa3, exit0:696 passed in7.54s.',
})
owners = read(Path('C:/Users/usuario/AppData/Local/BAXY/C03-process-repairs818-owners.json'))
assert owners['exit_code'] == 0 and owners['passed'] == 289 and owners['skipped'] == 0
write(out / 'OWNERS_DOTNET_EXIT.json', owners)
write(out / 'ISOLATED_REPRODUCTIONS.json', {
    '816': {'baseline_root': '4 failed/6 passed/0 omitted; session1577 chunk3ee77d exit1',
            'fixed_root': '284 passed/0 omitted; session2254 chunk1493da exit0',
            'baseline_private_log': 'C:/Users/usuario/AppData/Local/BAXY/C03-natural-context816-validation/baseline.log'},
    '817': read(Path('C:/Users/usuario/AppData/Local/BAXY/C03-process-truncation817-proposal/SUMMARY.json'))['captured_stub_regression'],
    '818': {'agent_owner': '158 passed/0 omitted in6s; no inference',
            'scope': '0/1 short rows ordinary;2/5/7 short rows dense;8/50 and512characters preserved; invalid/unverified/failed observations stay ordinary. Existing CPU and protocol budget checks retained.'},
})
for mode, prefix in [('Fast', 'VALIDATION'), ('Full', 'FULL')]:
    command = [shutil.which('pwsh'), '-NoProfile', '-File', 'scripts/test_source_quality.ps1', '-Mode', mode]
    assert command[0]
    log_path = private / (mode.lower() + '.log')
    with log_path.open('wb') as stream:
        process = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        write(out / (prefix + '_PROCESS.json'), {
            'utc': datetime.now(timezone.utc).isoformat(), 'pid': process.pid,
            'command': command, 'private_log': str(log_path),
            'source_pins_sha256': sha(out / 'SOURCE_PINS.json'), 'runner_sha256': sha(Path(__file__)),
        })
        print(json.dumps({'validation': mode, 'pid': process.pid, 'pins': len(pins)}), flush=True)
        code = process.wait()
    unchanged = all(sha(root / p) == h for p, h in pins.items())
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'exit_code': code,
              'source_pins_unchanged': unchanged, 'source_pins_sha256': sha(out / 'SOURCE_PINS.json'),
              'log_sha256': sha(log_path), 'private_log': str(log_path), 'adopted': False}
    write(out / (prefix + '_EXIT.json'), result)
    print(json.dumps({'validation': mode, **result}), flush=True)
    if code or not unchanged:
        raise SystemExit(code if code else 2)
