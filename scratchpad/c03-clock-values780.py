"""Fifty declared synthetic clock/calendar scenarios through the real local composer.

BAXY writer/validators/retries are active. This is not a native model comparison,
provider observation, graphical product run, human reserve or voice test.
"""
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess
import sys
import threading
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'CLOCK_VALUES780'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-clock-values780-private'
PREVIOUS = PRIVATE.parent / 'C03-status-batch779-private'
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    Path(path).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def utc():
    return datetime.now(timezone.utc).isoformat()


assert not OUT.exists() and not PRIVATE.exists()
assert psutil.virtual_memory().available >= 2700 * 2**20
busy = [p.info for p in psutil.process_iter(['pid', 'name', 'cmdline'])
        if (p.info['name'] or '').lower() in {'llama-server.exe', 'baxy.exe', 'baxy-core.exe', 'testhost.exe'}
        or any('pytest' in part for part in p.info['cmdline'] or [])]
assert not busy, busy
assert b'2298 passed, 1 skipped' in (Path(os.environ['TEMP']) / 'c03-clock778-final.log').read_bytes()
assert b'source_quality_gate_passed: mode=Fast' in (Path(os.environ['TEMP']) / 'c03-clock778-fast.log').read_bytes()
manifest = PRIVATE.parent.parent / 'BAXYRuntime/mind-runtime-v1.json'
config = read(manifest)
assert sha(manifest) == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
assert sha(config['gguf']) == '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
assert sha(config['llama_server']) == '38a9d28ea414442590486459a7d1f5e32655db83148b7a114b79cd1ad242946e'
pins = read(BASE / 'CLOCK_SCOPE778/SOURCE_PINS.json')
assert all(sha(ROOT / p) == h for p, h in pins.items())
source_paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard',
                                      '--', 'src', 'scripts', 'main.py'], cwd=ROOT, text=True).splitlines()
sources = {p: sha(ROOT / p) for p in sorted(set(source_paths)) if (ROOT / p).is_file()}
processes779 = read(PREVIOUS / 'processes.json')
prior_commands = [p['command'] for p in processes779.values() if p['name'].lower() == 'llama-server.exe']
assert len(prior_commands) == 1
previous_command = prior_commands[0]
captured = read(PREVIOUS / 'review.json')[0]['compose'][0]
template = json.loads(captured['situation'])
assert template['operation'] == 'system.time'
assert set(template['observed']) == {'version', 'utc', 'localUtcOffsetMinutes'}
OUT.mkdir()
PRIVATE.mkdir()
cases = []
values = [
    ('2026-01-01T00:15:00+00:00', -180),
    ('2026-12-31T23:45:00+00:00', 330),
    ('2024-03-01T00:05:00+00:00', -60),
    ('2025-03-01T00:05:00+00:00', -60),
    ('2026-02-01T00:10:00+00:00', -720),
    ('2026-04-01T00:10:00+00:00', -660),
    ('2026-05-01T00:10:00+00:00', -480),
    ('2026-06-01T00:10:00+00:00', -300),
    ('2026-07-01T00:10:00+00:00', -180),
    ('2026-08-01T00:10:00+00:00', -60),
    ('2026-09-01T12:00:00+00:00', 0),
    ('2026-10-01T11:59:00+00:00', 60),
    ('2026-11-01T23:59:00+00:00', 345),
    ('2026-12-01T23:59:00+00:00', 570),
    ('2026-01-15T12:00:00+00:00', 660),
    ('2026-02-15T23:30:00+00:00', 840),
    ('2026-03-15T00:00:00+00:00', 0),
    ('2026-04-15T12:00:00+00:00', 0),
    ('2026-05-15T18:07:00+00:00', -180),
    ('2026-06-15T02:09:00+00:00', 330),
    ('2026-07-15T08:03:00+00:00', -480),
    ('2026-08-15T15:42:00+00:00', 345),
    ('2026-09-15T04:58:00+00:00', 570),
    ('2026-10-15T21:11:00+00:00', -300),
    ('2026-11-15T09:26:00+00:00', -660),
]
questions = {
    'time': ['Dime qué hora es.', 'What time is it?', 'Baxy, dime the local time.'],
    'date': ['¿Qué fecha es hoy?', 'What is the current local date?', 'Mostrame the current date.'],
}
from datetime import timedelta
for index, (stamp, offset) in enumerate(values):
    local = datetime.fromisoformat(stamp) + timedelta(minutes=offset)
    for group in ['time', 'date']:
        situation = copy.deepcopy(template)
        situation['observed'].update(utc=stamp, localUtcOffsetMinutes=offset)
        language_index = (index + (group == 'date')) % 3
        cases.append({'id': f'clock780-{len(cases) + 1:02d}', 'group': group,
            'language': ['es', 'en', 'mixed'][language_index],
            'request': questions[group][language_index], 'situation': situation,
            'expected_clock': local.strftime('%H:%M'), 'expected_date': local.strftime('%Y-%m-%d'),
            'synthetic_observation': True,
            'criterion': 'Answer the requested local date/time from the supplied UTC plus explicit offset. '
                         'Accept equivalent natural wording and accurate12/24-hour forms; keep language and all additional claims faithful. '
                         'No stale value, UTC/local substitution, unsupported timezone/DST inference, empty answer or truncation.'})
assert len(cases) == 50
write(PRIVATE / 'cases.json', cases)
for key in list(os.environ):
    if key.startswith(('BAXY_MIND_', 'BAXY_VOICE_', 'BAXY_C03_', 'BAXY_FIELD_')) or key == 'PYTHONPATH':
        os.environ.pop(key)
environment = {'BAXY_MIND_LLM_GGUF': config['gguf'], 'BAXY_MIND_LLAMA_SERVER': config['llama_server'],
    'BAXY_MIND_NGL': str(config['ngl']), 'BAXY_MIND_CTX': '4096', 'BAXY_MIND_BATCH': '2048',
    'BAXY_MIND_UBATCH': '256', 'BAXY_MIND_KV_CACHE_TYPE': 'q8_0', 'BAXY_MIND_KV_OFFLOAD': '1',
    'BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH': str(PRIVATE / 'compose-audit.jsonl'),
    'BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT': '1', 'OMP_NUM_THREADS': '4', 'MKL_NUM_THREADS': '4',
    'TOKENIZERS_PARALLELISM': 'false'}
os.environ.update(environment)
prereg = {'utc': utc(), 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'candidate': 'CLOCK_SCOPE778, validated but not adopted yet', 'cases': len(cases),
    'groups': {'time': 25, 'date': 25},
    'case_sha256': sha(PRIVATE / 'cases.json'), 'source_pins': pins, 'sources': sources,
    'driver_sha256': sha(__file__), 'manifest_sha256': sha(manifest),
    'model_sha256': sha(config['gguf']), 'backend_sha256': sha(config['llama_server']),
    'template_source': '779 complete observed clock situation; only UTC, explicit offset and user request vary in declared synthetic fixtures.',
    'method': 'Real local BAXY composer with first draft and all retries retained; not bare/native model ranking. '
              'No sidecar/provider/App effects, UI, voice, reserve or automatic survey credit.',
    'environment': environment, 'previous779_server_command': previous_command,
    'environment_limit': 'Explicit OMP/MKL4 and TOKENIZERS=false match __main__ defaults; actual779 environment was not byte-captured.',
    'budget': {'per_request_seconds': 4, 'warmup_seconds': 90, 'wall_seconds': 600,
               'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768},
    'coverage_added': 0, 'quality_adjudicated': False}
write(OUT / 'PREREG.json', prereg)


class Client(LlmRuntime):
    case_id = None

    def _post(self, payload, *args, **kwargs):
        response = super()._post(payload, *args, **kwargs)
        with (PRIVATE / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'id': self.case_id, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
        return response


def normalized_command(command):
    value = list(command)
    value[value.index('--port') + 1] = '<port>'
    value[0] = str(Path(value[0]).resolve()).casefold()
    value[value.index('-m') + 1] = str(Path(value[value.index('-m') + 1]).resolve()).casefold()
    return value


client = Client()
gpu, ram = ProcessTreeGpuSampler(os.getpid()), RamSampler(os.getpid())
stop = threading.Event()
violations = []
replies = []
fatal = None
started = time.monotonic()


def guard():
    while not stop.wait(0.25):
        if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
            violations.append('owned_gpu_bound')
        if psutil.virtual_memory().available < 768 * 2**20:
            violations.append('system_free_ram_bound')
        if time.monotonic() - started > 600:
            violations.append('scenario_wall_time_bound')
        if violations:
            if client._process is not None:
                client._process.terminate()
            return


watcher = threading.Thread(target=guard, daemon=True)
try:
    gpu.start()
    ram.start()
    watcher.start()
    client.start_warmup()
    assert client.wait_warmup(90), 'warmup failed'
    command = client._server_command()
    assert normalized_command(command) == normalized_command(previous_command), (command, previous_command)
    write(OUT / 'READY.json', {'utc': utc(), 'runner': os.getpid(), 'server_pid': client._process.pid,
                             'server_command': command, 'same779_command_except_port': True})
    print(json.dumps({'ready': True, 'cases': len(cases)}), flush=True)
    for case in cases:
        assert not violations, violations
        client.case_id = case['id']
        client.begin_request(4)
        answer, error = None, None
        case_started = time.monotonic()
        try:
            answer = client.compose_user_message(case['request'], 'status',
                {'situation': json.dumps(case['situation'], ensure_ascii=False), 'requiredResponseWords': []})
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        finally:
            client.end_request()
        row = {'id': case['id'], 'answer': answer, 'error': error, 'seconds': time.monotonic() - case_started}
        replies.append(row)
        with (PRIVATE / 'replies.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        if len(replies) % 10 == 0:
            print(json.dumps({'completed': len(replies), 'registered': len(cases)}), flush=True)
except Exception as exc:
    fatal = f'{type(exc).__name__}: {exc}'
finally:
    client.close()
    stop.set()
    watcher.join(timeout=5)
    gpu.stop()
    ram.stop()
    result = {'utc': utc(), 'cases_completed': len(replies), 'cases_registered': len(cases), 'fatal': fatal,
              'violations': violations, 'seconds': time.monotonic() - started,
              'gpu_peak_mib': gpu.peak_mib, 'gpu_telemetry_available': gpu.telemetry_available,
              'ram_peak_mib': ram.peak_mib,
              'source_pins_unchanged': all(sha(ROOT / p) == h for p, h in pins.items()),
              'sources_unchanged': all(sha(ROOT / p) == h for p, h in sources.items()),
              'manifest_unchanged': sha(manifest) == prereg['manifest_sha256'],
              'driver_unchanged': sha(__file__) == prereg['driver_sha256'], 'quality_adjudicated': False}
    write(OUT / 'RESULT.json', result)
    print(json.dumps(result), flush=True)
raise SystemExit(0 if fatal is None and not violations and len(replies) == 50 else 1)
