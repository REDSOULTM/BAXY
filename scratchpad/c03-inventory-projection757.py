"""Same captured inventory and profile; change only the inventory writing clause."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-inventory-projection757-private'
SOURCE = PRIVATE.parent / 'C03-compose753-private'
OUT = ROOT / 'artifacts/comprobaciones/C03/INVENTORY_PROJECTION757'
INSTRUCTION = 'Projection-only: retain every title/process identity and all inventory metadata; omit unrequested per-window details from the narrator input.'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not OUT.exists() and not PRIVATE.exists()
assert not any((p.info['name'] or '').lower() in {'llama-server.exe', 'baxy.exe', 'baxy-core.exe', 'testhost.exe'}
               for p in psutil.process_iter(['name']))
assert psutil.virtual_memory().available >= 2700 * 2**20
prior = read(ROOT / 'artifacts/comprobaciones/C03/COMPOSE_BOUNDARY753/PREREG.json')
assert read(ROOT / 'artifacts/comprobaciones/C03/COMPOSE_BOUNDARY753/EXIT.json')['exit_code'] == 0
assert sha(prior['model']['path']) == prior['model']['sha256']
assert sha(prior['backend']['path']) == prior['backend']['sha256']
command = next(p['command'] for p in read(SOURCE / 'processes.json').values()
               if p['name'].lower() == 'llama-server.exe')
with socket.socket() as available:
    available.bind(('127.0.0.1', 0))
    port = available.getsockname()[1]
command[command.index('--port') + 1] = str(port)
requests = [json.loads(line) for line in (SOURCE / 'http-posts.jsonl').open(encoding='utf-8-sig')]
baseline = next(r['payload'] for r in requests if r['id'] == 3 and r['stage'] == 'request')
candidate = copy.deepcopy(baseline)
user = baseline['messages'][1]['content']
prefix, tail = user.split('\nsituation: ', 1)
observation, end = json.JSONDecoder().raw_decode(tail)
assert observation['operation'] == 'window.resolve'
assert json.dumps(observation, ensure_ascii=False) == tail[:end]
windows = observation['seen']['windows']
assert len(windows) == 20
projected = copy.deepcopy(observation)
projected['seen']['windows'] = [{key: value for key, value in window.items() if key in {'title', 'processName'}} for window in windows]
assert [(w.get('title'),w.get('processName')) for w in projected['seen']['windows']] == [(w.get('title'),w.get('processName')) for w in windows]
assert {k:v for k,v in projected['seen'].items() if k!='windows'} == {k:v for k,v in observation['seen'].items() if k!='windows'}
candidate['messages'][1]['content'] = prefix + '\nsituation: ' + json.dumps(projected, ensure_ascii=False) + tail[end:]
assert candidate['messages'][0] == baseline['messages'][0]
assert {k: v for k, v in candidate.items() if k != 'messages'} == {
    k: v for k, v in baseline.items() if k != 'messages'}
OUT.mkdir()
PRIVATE.mkdir()
planned = [{'arm': 'captured', 'payload': baseline}, {'arm': 'identity_projection', 'payload': candidate}]
write(PRIVATE / 'planned.json', planned)
plan = {'utc': datetime.now(timezone.utc).isoformat(), 'calls': 2, 'command': command,
        'source': 'COMPOSE_BOUNDARY753 HTTP request3, same frozen20-window observation',
        'change': INSTRUCTION, 'all_other_payload_fields_equal': True, 'window_count_preserved': len(windows), 'identity_sequence_preserved': True, 'inventory_metadata_preserved': True,
        'model': prior['model'], 'backend': prior['backend'], 'driver_sha256': sha(__file__),
        'source_llm_sha256': sha(ROOT / 'src/baxy_mind/llm.py'), 'planned_sha256': sha(PRIVATE / 'planned.json'),
        'source_requests_sha256': sha(SOURCE / 'http-posts.jsonl'),
        'limits': {'offline_observation_seconds': 15, 'unchanged_product_reference_seconds': 4, 'max_tokens': baseline['max_tokens'], 'gpu_stop_mib': 3800,
                   'minimum_free_ram_mib': 768},
        'criterion': 'Success reference remains complete untruncated final within4s. Offline observer waits15s to inspect the previously censored final; a late reply is not a4s success. Preserve all returned identities, '
                     'count and page scope. No shrinking the list, no factual invention, no changed validator.',
        'scope': 'Projection intervention after instruction-only754-756 did not complete either list. Inspect all identities and page scope under fixed256output tokens. Offline observation15s does not change any product deadline or the4s success reference. Server cwd remains binary folder rather than product sidecar folder; not a complete product timing replica or adoption.',
        'runtime_environment_defaults': {'OMP_NUM_THREADS': os.environ.get('OMP_NUM_THREADS', '4'), 'MKL_NUM_THREADS': os.environ.get('MKL_NUM_THREADS', '4'), 'TOKENIZERS_PARALLELISM': os.environ.get('TOKENIZERS_PARALLELISM', 'false')},
        'environment_source': 'src/baxy_mind/__main__.py:33-35;754 inherited absent values, so its environment was not identical to product753.'}
write(OUT / 'PREREG.json', plan)
endpoint = f'http://127.0.0.1:{port}'
stop, violations = threading.Event(), []
process = gpu = ram = watcher = None
results = []
started = time.monotonic()


def guard():
    while not stop.wait(.25):
        if (gpu.peak_mib or 0) >= 3800:
            violations.append('owned_gpu_bound')
        if psutil.virtual_memory().available < 768 * 2**20:
            violations.append('free_ram_bound')
        if time.monotonic() - started > 120:
            violations.append('diagnostic_wall_bound')
        if violations:
            if process.poll() is None:
                process.terminate()
            return


try:
    runtime_env = os.environ.copy()
    for name, value in plan['runtime_environment_defaults'].items():
        runtime_env.setdefault(name, value)
    with (PRIVATE / 'server.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=Path(command[0]).parent, env=runtime_env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    write(OUT / 'PROCESS.json', {'runner_pid': os.getpid(), 'server_pid': process.pid, 'command': command})
    gpu, ram = ProcessTreeGpuSampler(process.pid), RamSampler(process.pid)
    gpu.start()
    ram.start()
    watcher = threading.Thread(target=guard, daemon=True)
    watcher.start()
    while time.monotonic() - started < 90:
        assert process.poll() is None
        try:
            with urllib.request.urlopen(endpoint + '/health', timeout=1) as response:
                if json.load(response).get('status') == 'ok':
                    break
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(.25)
    else:
        raise TimeoutError('backend startup')
    for row in planned:
        before = time.monotonic()
        outcome = {'arm': row['arm']}
        request = urllib.request.Request(endpoint + '/v1/chat/completions',
                                         data=json.dumps(row['payload']).encode('utf-8'),
                                         headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                outcome['response'] = json.load(response)
        except Exception as error:
            outcome.update(error=type(error).__name__, detail=str(error))
            if isinstance(error, urllib.error.HTTPError):
                outcome['body'] = error.read().decode(errors='replace')
        outcome['seconds'] = time.monotonic() - before
        outcome['within4s'] = outcome['seconds'] <= 4
        results.append(outcome)
        write(PRIVATE / 'results.json', results)
        print(json.dumps({'arm': row['arm'], 'seconds': outcome['seconds'], 'error': outcome.get('error'),
                          'finish': (outcome.get('response', {}).get('choices') or [{}])[0].get('finish_reason')}), flush=True)
finally:
    stop.set()
    if process is not None:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=20)
    if watcher is not None:
        watcher.join(timeout=3)
    if gpu is not None:
        gpu.stop()
        ram.stop()
    write(OUT / 'RESULT.json', {'calls_completed': len(results), 'calls_planned': 2,
          'gpu_peak_mib': gpu.peak_mib if gpu else None, 'ram_peak_mib': ram.peak_mib if ram else None,
          'seconds': time.monotonic() - started, 'violations': violations,
          'driver_unchanged': sha(__file__) == plan['driver_sha256'],
          'source_unchanged': sha(ROOT / 'src/baxy_mind/llm.py') == plan['source_llm_sha256'],
          'scope': plan['scope'], 'quality_adjudicated': False})
