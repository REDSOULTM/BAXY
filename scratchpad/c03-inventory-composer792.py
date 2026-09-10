"""The same fifty frozen tasks per arm: original versus factual correction without rejected_draft.

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
import urllib.request

import psutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'INVENTORY_COMPOSER792'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-inventory-composer792-private'
PREVIOUS = PRIVATE.parent / 'C03-status-batch772-private'
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
validation = read(BASE / 'INVENTORY_IDENTITY791/VALIDATION.json')
assert validation['python_exit_code'] == validation['fast_exit_code'] == 0 and validation['terminal_collected']
manifest = PRIVATE.parent.parent / 'BAXYRuntime/mind-runtime-v1.json'
config = read(manifest)
assert sha(manifest) == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
assert sha(config['gguf']) == '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
assert sha(config['llama_server']) == '38a9d28ea414442590486459a7d1f5e32655db83148b7a114b79cd1ad242946e'
pins = read(BASE / 'INVENTORY_IDENTITY791/SOURCE_PINS.json')
assert all(sha(ROOT / p) == h for p, h in pins.items())
source_paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard',
                                      '--', 'src', 'scripts', 'main.py'], cwd=ROOT, text=True).splitlines()
sources = {p: sha(ROOT / p) for p in sorted(set(source_paths)) if (ROOT / p).is_file()}
processes772 = read(PREVIOUS / 'processes.json')
prior_commands = [p['command'] for p in processes772.values() if p['name'].lower() == 'llama-server.exe']
assert len(prior_commands) == 1
previous_command = prior_commands[0]
OUT.mkdir()
PRIVATE.mkdir()
cases = copy.deepcopy(read(PRIVATE.parent / 'C03-prose-sampling785-private/cases.json'))
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
    'candidate': 'INVENTORY_IDENTITY791 including787+789; validated, unadopted', 'cases': len(cases), 'executions': 100,
    'arms': {'A': 'Original composer payload', 'B': 'Remove only rejected_draft from Verified factual correction JSON at HTTP boundary'},
    'order': 'AB on even zero-based case index, BA on odd; same persistent backend, request context reset per execution',
    'groups': {'inventory': 26, 'memory': 23, 'clock': 1},
    'case_sha256': sha(PRIVATE / 'cases.json'), 'source_pins': pins, 'sources': sources,
    'driver_sha256': sha(__file__), 'manifest_sha256': sha(manifest),
    'model_sha256': sha(config['gguf']), 'backend_sha256': sha(config['llama_server']),
    'template_source': 'Same50 cases, questions, observations and whole-answer criteria as785/788/790. Each arm gets all50; first messages/caps/model/sampler/backend/deadlines identical. Only B retry rejected_draft is removed.',
    'method': 'Real local BAXY composer: all attempts logged before dispatch, successful responses and failed outcomes retained; not native model ranking. '
              'No sidecar/provider/App effects, UI, voice, reserve or automatic survey credit.',
    'environment': environment, 'previous772_server_command': previous_command,
    'environment_limit': 'Explicit OMP/MKL4 and TOKENIZERS=false match __main__ defaults; actual772 environment was not byte-captured.',
    'budget': {'per_request_seconds': '4 ordinary / 9 dense inventory, existing C#764 policy', 'warmup_seconds': 90, 'wall_seconds': 1200,
               'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768},
    'coverage_added': 0, 'quality_adjudicated': False}
# Capture candidate first requests without loading or invoking a model.
class Captured(BaseException):
    pass


class Capture(LlmRuntime):
    def __init__(self):
        self._gguf = config['gguf']
        self.payload = None
    def _post(self, payload):
        self.payload = copy.deepcopy(payload)
        raise Captured()


old_payloads = read(PRIVATE.parent / 'C03-inventory-composer788-private/expected-first.json')
expected_first = {}
for case in cases:
    capture = Capture()
    try:
        capture.compose_user_message(case['request'], 'status', {'situation': case['situation']})
    except Captured:
        pass
    candidate = capture.payload
    old = old_payloads[case['id']]
    assert candidate and candidate['max_tokens'] in {256,512}
    assert candidate == old, case['id']
    expected_first[case['id']] = candidate
write(PRIVATE / 'expected-first.json', expected_first)
prereg['first_payloads_sha256'] = sha(PRIVATE / 'expected-first.json')
prereg['first_payload_exact_parity788'] = 50
assert sha(PRIVATE / 'cases.json') == sha(PRIVATE.parent / 'C03-inventory-composer788-private/cases.json')
prereg['server_cwd'] = str(Path(config['python']).parent)
write(OUT / 'PREREG.json', prereg)


def remove_rejected_draft(payload):
    result = copy.deepcopy(payload)
    removed = []
    marker = "\nVerified factual correction: "
    for index, message in enumerate(result.get('messages', [])):
        content = message.get('content')
        if message.get('role') != 'user' or not isinstance(content, str) or marker not in content:
            continue
        before, rest = content.rsplit(marker, 1)
        correction, stop_at = json.JSONDecoder().raw_decode(rest)
        if not isinstance(correction, dict) or 'rejected_draft' not in correction:
            continue
        original = copy.deepcopy(correction)
        draft = correction.pop('rejected_draft')
        message['content'] = before + marker + json.dumps(correction, ensure_ascii=False) + rest[stop_at:]
        recovered, _ = json.JSONDecoder().raw_decode(message['content'].rsplit(marker, 1)[1])
        recovered['rejected_draft'] = draft
        assert recovered == original
        removed.append({'message_index': index, 'rejected_draft': draft})
    # Reconstruct the original object to prove there are no other differences.
    reconstructed = copy.deepcopy(result)
    for item in removed:
        index = item['message_index']
        reconstructed['messages'][index]['content'] = payload['messages'][index]['content']
    assert reconstructed == payload
    return result, removed


# Exact inherited payloads prove the intervention before any model inference.
prior_posts = PRIVATE.parent / 'C03-inventory-composer790-private/posts.jsonl'
probe_count = 0
with prior_posts.open(encoding='utf-8') as stream:
    for line in stream:
        prior = json.loads(line)
        actual, removed = remove_rejected_draft(prior['payload'])
        if prior['attempt'] == 1:
            assert actual == prior['payload'] and not removed
        probe_count += bool(removed)
assert probe_count > 0
prereg['intervention_replayed_on790_payloads'] = probe_count
write(OUT / 'PREREG.json', prereg)


class Client(LlmRuntime):
    case_id = None
    arm = None
    attempts = {}

    def _post(self, payload, *args, **kwargs):
        key = (self.case_id, self.arm)
        attempt = self.attempts.get(key, 0) + 1
        self.attempts[key] = attempt
        original_payload = copy.deepcopy(payload)
        removed = []
        if self.arm == 'B':
            payload, removed = remove_rejected_draft(payload)
        if attempt == 1:
            assert payload == original_payload == expected_first[self.case_id]
            assert not removed
        before = time.monotonic()

        def attempt_event(state, **fields):
            with (PRIVATE / 'attempts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'id': self.case_id, 'arm': self.arm, 'attempt': attempt,
                                         'state': state, 'utc': utc(), **fields}, ensure_ascii=False) + '\n')
        attempt_event('started', payload=payload, original_payload=original_payload, removed=removed)
        try:
            response = super()._post(payload, *args, **kwargs)
        except Exception as exc:
            attempt_event('failed', error=f'{type(exc).__name__}: {exc}', seconds=time.monotonic() - before)
            raise
        attempt_event('succeeded', seconds=time.monotonic() - before)
        record = {'id': self.case_id, 'arm': self.arm, 'attempt': attempt, 'payload': payload,
                  'original_payload': original_payload, 'removed': removed,
                  'response': response, 'post_seconds': time.monotonic() - before}
        try:
            with urllib.request.urlopen(self._endpoint + '/slots', timeout=2) as stream:
                record['slots_after'] = json.load(stream)
        except Exception as exc:
            record['slots_unavailable'] = str(exc)
        with (PRIVATE / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
        return response


def normalized_command(command):
    value = list(command)
    value[value.index('--port') + 1] = '<port>'
    value[0] = str(Path(value[0]).resolve()).casefold()
    value[value.index('-m') + 1] = str(Path(value[value.index('-m') + 1]).resolve()).casefold()
    return value


os.chdir(Path(config['python']).parent)
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
        if time.monotonic() - started > 1200:
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
                             'server_command': command, 'same772_command_except_port': True})
    print(json.dumps({'ready': True, 'cases': len(cases)}), flush=True)
    executions = [(case, arm) for index, case in enumerate(cases) for arm in (('A', 'B') if index % 2 == 0 else ('B', 'A'))]
    for case, arm in executions:
        assert not violations, violations
        client.arm = arm
        client.case_id = case['id']
        situation = case['situation']
        windows = (situation.get('observed') or {}).get('windows')
        dense = (situation.get('operation') == 'window.resolve'
                 and situation.get('verified') is True and situation.get('succeeded') is True
                 and isinstance(windows, list)
                 and (len(windows) >= 8 or len(json.dumps(windows, ensure_ascii=False, separators=(',',':'))) >= 512))
        request_budget = 9 if dense else 4
        client.begin_request(request_budget)
        answer, error = None, None
        case_started = time.monotonic()
        try:
            answer = client.compose_user_message(case['request'], 'status',
                {'situation': json.dumps(case['situation'], ensure_ascii=False), 'requiredResponseWords': []})
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        finally:
            client.end_request()
        row = {'id': case['id'], 'arm': arm, 'request_budget_seconds': request_budget, 'answer': answer, 'error': error, 'attempts': client.attempts.get((case['id'], arm), 0), 'seconds': time.monotonic() - case_started}
        replies.append(row)
        with (PRIVATE / 'replies.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        if len(replies) % 10 == 0:
            print(json.dumps({'completed': len(replies), 'registered': 100}), flush=True)
except Exception as exc:
    fatal = f'{type(exc).__name__}: {exc}'
finally:
    client.close()
    stop.set()
    watcher.join(timeout=5)
    gpu.stop()
    ram.stop()
    result = {'utc': utc(), 'executions_completed': len(replies), 'executions_registered': 100, 'distinct_cases': len(cases), 'fatal': fatal,
              'violations': violations, 'seconds': time.monotonic() - started,
              'gpu_peak_mib': gpu.peak_mib, 'gpu_telemetry_available': gpu.telemetry_available,
              'ram_peak_mib': ram.peak_mib,
              'source_pins_unchanged': all(sha(ROOT / p) == h for p, h in pins.items()),
              'sources_unchanged': all(sha(ROOT / p) == h for p, h in sources.items()),
              'manifest_unchanged': sha(manifest) == prereg['manifest_sha256'],
              'driver_unchanged': sha(__file__) == prereg['driver_sha256'], 'quality_adjudicated': False}
    write(OUT / 'RESULT.json', result)
    print(json.dumps(result), flush=True)
raise SystemExit(0 if fatal is None and not violations and len(replies) == 100 else 1)
