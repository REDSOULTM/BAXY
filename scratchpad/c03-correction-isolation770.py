"""Bounded 2x2 diagnostic of retry information; immutable product, one observation."""
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
from baxy_mind.llm import LlmRuntime, _compose_situation_payload

BASE = ROOT / 'artifacts/comprobaciones/C03'
SOURCE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-status-batch769-private'
PRIVATE = SOURCE.parent / 'C03-correction-isolation770-private'
OUT = BASE / 'CORRECTION_ISOLATION770'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not OUT.exists() and not PRIVATE.exists()
exit769 = read(BASE / 'STATUS_BATCH769/EXIT.json')
assert exit769['exit_code'] == 0 and all(exit769[k] for k in [
    'manifest_unchanged', 'sources_unchanged', 'source768_unchanged', 'source764_unchanged',
    'runner_unchanged', 'app_dll_unchanged'])
assert not any((p.info['name'] or '').lower() in {'llama-server.exe', 'baxy.exe', 'baxy-core.exe', 'testhost.exe'}
               for p in psutil.process_iter(['name']))
assert psutil.virtual_memory().available >= 2700 * 2**20
prior = read(BASE / 'STATUS_BATCH769/PREREG.json')
assert sha(prior['model']['path']) == prior['model']['sha256']
assert sha(prior['backend']['path']) == prior['backend']['sha256']
source_pins = {**read(BASE / 'INVENTORY_CORRECTION768/SOURCE_PINS.json'),
               **read(BASE / 'DENSE_INVENTORY764/SOURCE_PINS.json')}
assert all(sha(ROOT / p) == h for p,h in source_pins.items())
case = next(r for r in read(SOURCE / 'review.json') if r['case_id'] == 'H0023')
draft = next(r for r in case['compose'] if r.get('stage') == 'first' and r.get('reason') == 'extra_claim')
observed = copy.deepcopy(draft['payload']['seen'])
del observed['returnedPageScope']
situation = {'kind': 'operation', 'operation': 'window.resolve', 'polarity': 'success',
             'verified': True, 'succeeded': True, 'observed': observed}
assert _compose_situation_payload(situation, 'es', case['text']) == draft['payload']


class Captured(BaseException):
    pass


class Capture(LlmRuntime):
    def __init__(self):
        self._gguf = prior['model']['path']
        self.requests = []

    def _post(self, payload):
        self.requests.append(copy.deepcopy(payload))
        if len(self.requests) == 2:
            raise Captured()
        return {'choices': [{'message': {'content': draft['draft']}, 'finish_reason': 'stop'}]}


capture = Capture()
try:
    capture.compose_user_message(case['text'], 'status', {'situation': situation})
except Captured:
    pass
assert len(capture.requests) == 2
baseline = capture.requests[1]
user, feedback_text = baseline['messages'][1]['content'].split('\nVerified factual correction: ')
feedback = json.loads(feedback_text)
assert feedback['rejected_draft'] == draft['draft'] and 'unsupported_claim' in feedback
instruction = (' The observation contains no window opening times, so it does not establish '
               'which windows are newest or oldest. Correct that claim using only the observed facts.')
planned = []
for arm, keep_draft, clarify in [('A_current', True, False), ('B_no_rejected_draft', False, False),
                                ('D_no_draft_explicit_cause', False, True), ('C_explicit_cause', True, True)]:
    payload = copy.deepcopy(baseline)
    info = copy.deepcopy(feedback)
    if not keep_draft:
        del info['rejected_draft']
    payload['messages'][1]['content'] = user + '\nVerified factual correction: ' + json.dumps(info, ensure_ascii=False)
    if clarify:
        payload['messages'][0]['content'] += instruction
    assert {k:v for k,v in payload.items() if k != 'messages'} == {k:v for k,v in baseline.items() if k != 'messages'}
    planned.append({'arm': arm, 'keep_rejected_draft': keep_draft, 'explicit_cause': clarify, 'payload': payload})
assert planned[0]['payload'] == baseline
command = next(p['command'] for p in read(SOURCE / 'processes.json').values()
               if p['name'].lower() == 'llama-server.exe')
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
command[command.index('--port') + 1] = str(port)
OUT.mkdir()
PRIVATE.mkdir()
write(PRIVATE / 'planned.json', planned)
write(PRIVATE / 'reconstructed.json', {'user_text': case['text'], 'situation': situation, 'draft': draft['draft'],
                                      'captured_payload': draft['payload'], 'built_requests': capture.requests})
plan = {'utc': datetime.now(timezone.utc).isoformat(), 'calls': len(planned), 'command': command,
    'factors': ['Retain or remove rejected_draft only in existing feedback object', 'Add or omit one explicit statement of the same unsupported chronology cause in system'],
    'order': [r['arm'] for r in planned], 'model': prior['model'], 'backend': prior['backend'],
    'driver_sha256': sha(__file__), 'source_pins': source_pins, 'planned_sha256': sha(PRIVATE / 'planned.json'),
    'source_review_sha256': sha(SOURCE / 'review.json'), 'reconstructed_sha256': sha(PRIVATE / 'reconstructed.json'),
    'raw_input_exact_replay': False, 'projected_payload_exactly_equal': True,
    'input_limit': 'audit.situation is truncated at2048characters; reconstruct verified envelope with equal projected facts. Current composer builds both requests with one captured draft stub. No assertion of raw product request byte identity.',
    'limits': {'observe_seconds_per_call': 15, 'max_tokens_unchanged': baseline['max_tokens'], 'gpu_stop_mib': 3800, 'free_ram_min_mib': 768, 'wall_seconds': 150},
    'criterion': 'All20 returned identities including multiplicity, partial20/25 scope, no unsupported opening chronology or other invented facts; score separately from elapsed time. A single isolated reply does not establish retry fits total product budget.',
    'scope': 'Four development calls on one frozen observation, causal diagnostic of two retry factors. Single pass/fixed order/cache may affect latency; no model ranking, survey, fresh reserve, UI, voice or product acceptance.',
    'environment_defaults': {'OMP_NUM_THREADS': os.environ.get('OMP_NUM_THREADS', '4'), 'MKL_NUM_THREADS': os.environ.get('MKL_NUM_THREADS', '4'), 'TOKENIZERS_PARALLELISM': os.environ.get('TOKENIZERS_PARALLELISM', 'false')}}
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
        if time.monotonic() - started > 150:
            violations.append('diagnostic_wall_bound')
        if violations:
            if process.poll() is None:
                process.terminate()
            return


try:
    env = os.environ.copy()
    for name,value in plan['environment_defaults'].items():
        env.setdefault(name, value)
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
    for row in planned:
        before = time.monotonic()
        outcome = {'arm': row['arm']}
        request = urllib.request.Request(endpoint + '/v1/chat/completions',
            data=json.dumps(row['payload']).encode('utf-8'), headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                outcome['response'] = json.load(response)
        except Exception as error:
            outcome.update(error=type(error).__name__, detail=str(error))
        outcome['seconds'] = time.monotonic() - before
        results.append(outcome)
        write(PRIVATE / 'results.json', results)
        print(json.dumps({k:outcome[k] for k in ['arm', 'seconds']}), flush=True)
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
