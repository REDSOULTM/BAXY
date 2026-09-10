"""Paired50-case output-budget diagnostic; immutable product,100calls."""
from datetime import datetime, timezone
from pathlib import Path
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
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

BASE = ROOT / 'artifacts/comprobaciones/C03'
SOURCE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-status-batch772-private'
PRIVATE = SOURCE.parent / 'C03-inventory-budget786-private'
OUT = BASE / 'INVENTORY_BUDGET786'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not OUT.exists() and not PRIVATE.exists()
assert not any((p.info['name'] or '').lower() in {'llama-server.exe', 'baxy.exe', 'baxy-core.exe', 'testhost.exe'}
               for p in psutil.process_iter(['name']))
assert psutil.virtual_memory().available >= 2700 * 2**20
prior = read(BASE / 'STATUS_BATCH772/PREREG.json')
assert sha(prior['model']['path']) == prior['model']['sha256']
assert sha(prior['backend']['path']) == prior['backend']['sha256']
source_pins = {**read(BASE / 'NAMED_CLOCK783/PUBLICATION_SOURCE_PINS.json'),
               **read(BASE / 'DENSE_INVENTORY764/SOURCE_PINS.json')}
assert all(sha(ROOT / p) == h for p,h in source_pins.items())
reference_private = SOURCE.parent / 'C03-prose-sampling785-private'
reference = read(BASE / 'PROSE_SAMPLING785/PREREG.json')
assert sha(reference_private / 'cases.json') == reference['cases_sha256']
assert sha(reference_private / 'planned.json') == reference['planned_sha256']
reference_pins = read(BASE / 'PROSE_SAMPLING785/PINS.json')
assert sha(BASE / 'PROSE_SAMPLING785/ADJUDICATION.json') == reference_pins['files']['ADJUDICATION.json']
panel = read(reference_private / 'cases.json')
reference_payloads = {p['case_id']:p['payload'] for p in read(reference_private / 'planned.json')
                      if p['arm'] == 'A_registered_greedy'}
assert len(panel) == len(reference_payloads) == 50
planned=[]
for index,case in enumerate(panel):
    baseline = reference_payloads[case['id']]
    assert baseline['temperature'] == 0 and baseline['max_tokens'] == 256
    assert baseline.get('cache_prompt') is False
    variants=[]
    for arm,cap in [('A_original_256',256),('B_output_512',512)]:
        payload=copy.deepcopy(baseline)
        payload['max_tokens']=cap
        assert {k:v for k,v in payload.items() if k != 'max_tokens'} == {k:v for k,v in baseline.items() if k != 'max_tokens'}
        variants.append({'arm':arm,'case_id':case['id'],'payload':payload})
    if index % 2:
        variants.reverse()
    planned.extend(variants)
command=next(p['command'] for p in read(SOURCE/'processes.json').values() if p['name'].lower()=='llama-server.exe')
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
command[command.index('--port')+1]=str(port)
OUT.mkdir();PRIVATE.mkdir()
write(PRIVATE/'cases.json',panel);write(PRIVATE/'planned.json',planned)
plan={'utc':datetime.now(timezone.utc).isoformat(),'calls':len(planned),'cases':len(panel),'command':command,
    'model':prior['model'],'backend':prior['backend'],'source_pins':source_pins,'driver_sha256':sha(__file__),
    'planned_sha256':sha(PRIVATE/'planned.json'),'cases_sha256':sha(PRIVATE/'cases.json'),
    'reference_cases_sha256':reference['cases_sha256'],
    'reference_adjudication_sha256':reference_pins['files']['ADJUDICATION.json'],
    'intervention':'Same50 frozen785 cases and exact A_registered_greedy HTTP bodies. A max_tokens256 versus B max_tokens512; only output cap differs. Alternating arm order. Product source/prompt/sampler unchanged.',
    'inheritance':'785 found17 length cuts across3arms and sampler alone did not resolve the category.754-759/768/771 showed limits of additional prompt wording.764 supplies dense-inventory9s model/10s app time, distinct from Python output cap256.',
    'limits':{'observe_seconds_per_call':15,'output_caps':[256,512],'gpu_stop_mib':3800,'free_ram_min_mib':768,'wall_seconds':900},
    'criterion':'Same frozen785 criteria and whole-answer adjudication policy: requested facts, title/process identities and exact multiplicity, scope, quantities, subject, language and no unsupported chronology. Keep truncation, omissions, subject and value errors separate. No relaxation for a longer response.',
    'scope':'First-draft BAXY-context output-budget diagnostic; not native-model ranking, recommended-recipe reference, complete product/UI/voice/reserve acceptance or automatic survey credit. No product adoption. All user data stays local.',
    'environment_defaults':{'OMP_NUM_THREADS':'4','MKL_NUM_THREADS':'4','TOKENIZERS_PARALLELISM':'false'}}
write(OUT / 'PREREG.json', plan)
stop = threading.Event()
violations, results = [], []
process = gpu = ram = watcher = None
started = time.monotonic()


def guard():
    while not stop.wait(.25):
        if (gpu.peak_mib or 0) >= 3800:
            violations.append('owned_gpu_bound')
        if psutil.virtual_memory().available < 768 * 2**20:
            violations.append('free_ram_bound')
        if time.monotonic() - started > 900:
            violations.append('diagnostic_wall_bound')
        if violations:
            if process.poll() is None:
                process.terminate()
            return


try:
    env = os.environ.copy()
    for name,value in plan['environment_defaults'].items():
        env[name] = value
    with (PRIVATE / 'server.log').open('w', encoding='utf-8') as log:
        runtime = read(PRIVATE.parent.parent / 'BAXYRuntime/mind-runtime-v1.json')
        process = subprocess.Popen(command, cwd=Path(runtime['python']).parent, env=env,
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    write(OUT / 'PROCESS.json', {'runner_pid': os.getpid(), 'server_pid': process.pid})
    gpu, ram = ProcessTreeGpuSampler(process.pid), RamSampler(process.pid)
    gpu.start(); ram.start()
    watcher = threading.Thread(target=guard, daemon=True)
    watcher.start()
    endpoint = f'http://127.0.0.1:{port}'
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
    try:
        with urllib.request.urlopen(endpoint + '/props', timeout=2) as response:
            write(PRIVATE / 'server-props.json', json.load(response))
    except (urllib.error.URLError, TimeoutError) as error:
        write(PRIVATE / 'server-props.json', {'unavailable': str(error)})
    slots_available = True
    for row in planned:
        assert not violations, violations
        before = time.monotonic()
        outcome = {'arm': row['arm'], 'case_id': row['case_id']}
        request = urllib.request.Request(endpoint + '/v1/chat/completions',
            data=json.dumps(row['payload']).encode('utf-8'), headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                outcome['response'] = json.load(response)
        except Exception as error:
            outcome.update(error=type(error).__name__, detail=str(error))
        outcome['seconds'] = time.monotonic() - before
        if slots_available:
            try:
                with urllib.request.urlopen(endpoint + '/slots', timeout=2) as response:
                    outcome['slots_after'] = json.load(response)
            except (urllib.error.URLError, TimeoutError) as error:
                outcome['slots_telemetry_unavailable'] = str(error)
                slots_available = False
        results.append(outcome)
        write(PRIVATE / 'results.json', results)
        if len(results) % 10 == 0:
            print(json.dumps({'completed': len(results), 'planned': len(planned)}), flush=True)
finally:
    stop.set()
    if process is not None:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=20)
    if watcher is not None:
        watcher.join(timeout=3)
    if gpu is not None:
        gpu.stop(); ram.stop()
    write(OUT / 'RESULT.json', {'calls_completed': len(results), 'calls_planned': len(planned),
        'seconds': time.monotonic() - started, 'gpu_peak_mib': gpu.peak_mib if gpu else None,
        'ram_peak_mib': ram.peak_mib if ram else None, 'violations': violations,
        'driver_unchanged': sha(__file__) == plan['driver_sha256'],
        'sources_unchanged': all(sha(ROOT / p) == h for p,h in source_pins.items()),
        'quality_adjudicated': False, 'scope': plan['scope']})
