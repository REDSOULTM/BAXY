"""Repeat Fast/Full after updating three current-source identity declarations."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

import psutil

root = Path(__file__).resolve().parents[1]
parent = root / 'artifacts/comprobaciones/C03/PROCESS_REPAIRS818'
out = parent / 'FULL_RETRY1'
private = Path('C:/Users/usuario/AppData/Local/BAXY/C03-process-repairs818-private/full-retry1')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    assert not path.exists(), path
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())


assert read(parent / 'FULL_EXIT.json')['exit_code'] == 1
assert read(parent / 'FULL_RESULT.json')['python']['failed'] == 3
assert not out.exists() and not private.exists()
old = read(parent / 'SOURCE_PINS.json')
changed = {
    'experiments/stt_quality/evaluate_reserved_stt.py',
    'experiments/stt_quality/audit_fresh_postweight_stt_sources.py',
    'tests/test_price_v8_veto_damage_by_cause.py',
}
assert all(sha(root / p) == h for p, h in old.items() if p not in changed)
assert all(sha(root / p) != old[p] for p in changed)
busy = [p.info for p in psutil.process_iter(['name', 'pid', 'cmdline'])
        if (p.info['name'] or '').lower() in {'llama-server.exe', 'baxy.exe', 'baxy-core.exe', 'testhost.exe'}
        or any('pytest' in part for part in p.info['cmdline'] or [])]
assert not busy, busy
out.mkdir()
private.mkdir()
pins = {p: sha(root / p) for p in old}
assert len(pins) == 33
write(out / 'SOURCE_PINS.json', pins)
for p in pins:
    target = private / 'source' / p
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / p, target)
for name in ('OWNERS_PYTHON_EXIT.json', 'OWNERS_DOTNET_EXIT.json'):
    assert read(parent / name)['exit_code'] == 0
    shutil.copyfile(parent / name, out / name)
write(out / 'IDENTITY_REPAIR.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'candidate': 818, 'revision': 1,
    'scope': 'Three current-source identities only. Product runtime files remain byte-identical to original818.',
    'changed': {p: {'before': old[p], 'after': pins[p]} for p in sorted(changed)},
    'program_tree': {'python_files': 407,
                     'before': 'f5097ca94014924aadd6e60006c9f1ebc68f17cba7e1e7fdb0600e8c1af3114f',
                     'after': '26d5c4919721acf8f84da85545d0cdd024ab255ddbb90473acb04b2d89fefb91'},
    'llm_current_sha256': pins['src/baxy_mind/llm.py'],
    'owners_reused': 'Original818 runtime owners are copied byte-for-byte; no runtime source changed. Additional reference owners recorded separately.',
    'historical_evidence': 'No campaign, consumed population, frozen historical identity or original red Full is reissued. Mismatched historical audio preregistrations continue to be rejected.',
    'original_full_exit_sha256': sha(parent / 'FULL_EXIT.json'),
    'original_source_pins_sha256': sha(parent / 'SOURCE_PINS.json'),
    'adopted': False,
})
write(out / 'OWNERS_REFERENCE_EXIT.json', {
    'exit_code': 0, 'passed': 17, 'skipped': 1, 'seconds': 1.93,
    'command': 'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8 -m pytest -q tests/test_price_v8_veto_damage_by_cause.py tests/test_stt_quality_evaluators.py',
    'evidence': 'Root command chunkdb16e9:17 passed,1 skipped in1.93s.',
    'skip': 'Environmental absence of blind-campaign inputs, test_stt_quality_evaluators.py:122. Not counted as passed; no data campaign reopened.',
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
        print(json.dumps({'retry': 1, 'validation': mode, 'pid': process.pid}), flush=True)
        code = process.wait()
    unchanged = all(sha(root / p) == h for p, h in pins.items())
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'exit_code': code,
              'source_pins_unchanged': unchanged, 'source_pins_sha256': sha(out / 'SOURCE_PINS.json'),
              'log_sha256': sha(log_path), 'private_log': str(log_path), 'adopted': False,
              'original_failure': '../FULL_EXIT.json', 'identity_repair': 'IDENTITY_REPAIR.json'}
    write(out / (prefix + '_EXIT.json'), result)
    print(json.dumps({'retry': 1, 'validation': mode, **result}), flush=True)
    if code or not unchanged:
        raise SystemExit(code if code else 2)
