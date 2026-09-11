"""Eight sealed OCR development cases through the unchanged local composer.

Root must supply the collected Full and final source-pin byte hashes. No grading.
Prepared without execution; the only input facts are the unchanged OCR Result.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import base64
import copy
import functools
import hashlib
import http.client
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import weakref

import psutil

ROOT = Path('D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO')
BASE = ROOT / 'artifacts/comprobaciones/C03'
VALIDATION = BASE / 'OBSERVATION829/UNICODE_RETRY2'
LOCAL = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
PREP = LOCAL / 'C03-ocr832-prep-proposal'
OUT = BASE / 'OCR_COMPOSER832'
PRIVATE = LOCAL / 'C03-ocr-composer832-private'
MANIFEST = LOCAL.parent / 'BAXYRuntime/mind-runtime-v1.json'
PLAN_SHA = '8a8e5810447a37a5eb10f6b2e6aa4d40df00f004950684c387a6dfe1b9934f41'
CASES_SHA = 'de8f9d5dbc768d42ec54fae7074d38ce7ecc30bafbcbf0372dfa86590a51eeef'
ORIGINAL_PINS_SHA = 'f4f206175dbde85b2f335654fe11508d33979ef28705a6deacd4472b2f02f25e'
MANIFEST_SHA = '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
MODEL_SHA = '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
BACKEND_SHA = '38a9d28ea414442590486459a7d1f5e32655db83148b7a114b79cd1ad242946e'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    Path(path).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def utc():
    return datetime.now(timezone.utc).isoformat()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def normalized_command(command):
    value = list(command)
    value[value.index('--port') + 1] = '<port>'
    value[0] = str(Path(value[0]).resolve()).casefold()
    value[value.index('-m') + 1] = str(Path(value[value.index('-m') + 1]).resolve()).casefold()
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-full-sha256', required=True)
    parser.add_argument('--expected-pins-sha256', required=True)
    args = parser.parse_args()
    for value in (args.expected_full_sha256, args.expected_pins_sha256):
        require(len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'Expected lowercase SHA256')
    require(not OUT.exists() and not PRIVATE.exists(), 'Output already exists; no automatic rerun')
    require(Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, text=True).strip()).resolve() == ROOT.resolve(), 'Wrong repository')
    require(subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip() == 'Goal-c03', 'Wrong branch')
    require(psutil.virtual_memory().available >= 2700 * 2**20, 'Initial free RAM below 2700 MiB')
    own_pids = {os.getpid()}
    current_process = psutil.Process()
    parent_process = current_process.parent()
    if parent_process is not None:
        try:
            is_own_venv_launcher = (
                Path(parent_process.exe()).resolve() == Path(sys.executable).resolve()
                and Path(current_process.exe()).resolve() == Path(sys._base_executable).resolve()
                and Path(parent_process.exe()).resolve() != Path(current_process.exe()).resolve()
                and parent_process.cmdline()[1:] == current_process.cmdline()[1:]
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            is_own_venv_launcher = False
        if is_own_venv_launcher:
            own_pids.add(parent_process.pid)
    busy = []
    for process in psutil.process_iter(['pid', 'name', 'cmdline']):
        if process.pid in own_pids:
            continue
        info = process.info
        name = (info['name'] or '').lower()
        command = ' '.join(info['cmdline'] or []).lower()
        if (name in {'llama-server.exe', 'baxy.exe', 'baxy-core.exe', 'testhost.exe', 'msbuild.exe', 'vbcscompiler.exe'}
                or (name == 'dotnet.exe' and any(token in command for token in (' build', ' test', 'msbuild', 'vstest')))
                or (name in {'python.exe', 'pythonw.exe', 'py.exe'} and ('pytest' in command or 'scratchpad/c03-' in command.replace('\\', '/')))):
            busy.append({'pid': info['pid'], 'name': name})
    require(not busy, f'Busy processes: {busy}')
    original_pins_path = BASE / 'OBSERVATION829/SOURCE_PINS.json'
    require(sha(original_pins_path) == ORIGINAL_PINS_SHA, 'Original829 pin seal changed')
    pins_path = VALIDATION / 'SOURCE_PINS.json'
    full_path = VALIDATION / 'FULL_EXIT.json'
    require(sha(pins_path) == args.expected_pins_sha256, 'Final source pin seal mismatch')
    require(sha(full_path) == args.expected_full_sha256, 'Full receipt seal mismatch')
    pins, full = read(pins_path), read(full_path)
    require(len(pins) == 46 and set(pins) == set(read(original_pins_path)), 'Expected exact 46 source paths')
    require(type(full.get('exit_code')) is int and full['exit_code'] == 0, 'Full not green')
    require(full.get('source_pins_unchanged') is True, 'Full pins not verified')
    require(full.get('source_pins_sha256') == args.expected_pins_sha256, 'Full does not attest final pins')
    require(sha(full['private_log']) == full['log_sha256'], 'Full log seal mismatch')
    require(sha(PREP / 'PLAN.json') == PLAN_SHA and sha(PREP / 'CASES.json') == CASES_SHA, 'Panel seals changed')
    plan, panel = read(PREP / 'PLAN.json'), read(PREP / 'CASES.json')
    require(plan['seal']['cases_sha256'] == CASES_SHA, 'Plan/cases mismatch')
    fixture_path, image_path = Path(plan['source']['observation_json_path']), Path(plan['source']['image_path'])
    fixture_sha, image_sha = plan['source']['observation_json_sha256'], plan['source']['image_sha256']
    require(sha(fixture_path) == fixture_sha and sha(image_path) == image_sha, 'Fixture/image seal mismatch')
    fixture = read(fixture_path)
    require(fixture['receipt']['Operation'] == 'ocr.read' and fixture['receipt']['Verified'] is True, 'Not verified OCR receipt')
    observed = fixture['receipt']['Result']
    cases = [{'id': case['case_id'], 'user_message': case['user_message']} for case in panel['cases']]
    require(len(cases) == 8 and [c['id'] for c in cases] == plan['cases']['execution_order'], 'Expected eight sealed cases')
    require(sha(MANIFEST) == MANIFEST_SHA, 'Manifest changed')
    config = read(MANIFEST)
    require(sha(config['gguf']) == MODEL_SHA and sha(config['llama_server']) == BACKEND_SHA, 'Model/backend changed')
    previous_path = LOCAL / 'C03-status-batch772-private/processes.json'
    previous = [p['command'] for p in read(previous_path).values() if p['name'].lower() == 'llama-server.exe']
    require(len(previous) == 1, 'Expected one inherited server command')
    previous_command = previous[0]
    sources_list = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', 'src', 'scripts', 'main.py'], cwd=ROOT, text=True).splitlines()
    sources = {p: sha(ROOT / p) for p in sorted(set(sources_list)) if (ROOT / p).is_file()}
    seals = {str(ROOT / p): h for p, h in pins.items()}
    seals.update({str(PREP / 'PLAN.json'): PLAN_SHA, str(PREP / 'CASES.json'): CASES_SHA,
        str(fixture_path): fixture_sha, str(image_path): image_sha, str(MANIFEST): MANIFEST_SHA,
        str(config['gguf']): MODEL_SHA, str(config['llama_server']): BACKEND_SHA,
        str(pins_path): args.expected_pins_sha256, str(full_path): args.expected_full_sha256,
        str(original_pins_path): ORIGINAL_PINS_SHA, str(full['private_log']): full['log_sha256'],
        str(previous_path): sha(previous_path), str(Path(__file__).resolve()): sha(__file__)})

    def check_seals():
        return all(sha(path) == expected for path, expected in seals.items()) and all(sha(ROOT / p) == h for p, h in sources.items())

    require(check_seals(), 'Preflight source/asset seal mismatch')
    OUT.mkdir()
    PRIVATE.mkdir()
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
    sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
    from baxy_mind.llm import LlmRuntime
    import baxy_mind.llm as llm_module
    import baxy_mind.llm_transport as transport
    from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

    capture_lock = threading.Lock()
    capture_context = threading.local()

    def append(name, value):
        with capture_lock:
            with (PRIVATE / name).open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(value, ensure_ascii=False) + '\n')

    class WireCapture:
        """Observe existing transport calls; never read, resend or parse for it."""

        def __init__(self):
            self.patches = []
            self.responses = weakref.WeakKeyDictionary()
            self.counter = 0

        def next_id(self, prefix):
            with capture_lock:
                self.counter += 1
                return f'{prefix}-{self.counter}'

        def event(self, state, **fields):
            logical = getattr(capture_context, 'logical', None)
            if logical is not None:
                append('physical-http.jsonl', {'utc': utc(), 'logical_post_id': logical,
                    'transport_attempt_id': getattr(capture_context, 'transport_attempt', None),
                    'physical_id': getattr(capture_context, 'physical', None), 'state': state, **fields})

        def patch(self, owner, name, wrapper):
            original = getattr(owner, name)
            self.patches.append((owner, name, original))
            setattr(owner, name, wrapper(original))

        def branch(self, name):
            def decorate(original):
                @functools.wraps(original)
                def wrapped(*args, **kwargs):
                    if getattr(capture_context, 'logical', None) is None:
                        return original(*args, **kwargs)
                    previous = (getattr(capture_context, 'transport_attempt', None), getattr(capture_context, 'physical', None))
                    capture_context.transport_attempt = self.next_id('transport')
                    capture_context.physical = None
                    started_at = time.monotonic()
                    self.event('transport_attempt_started', branch=name)
                    try:
                        result = original(*args, **kwargs)
                    except BaseException as exc:
                        self.event('transport_attempt_failed', branch=name, error=f'{type(exc).__name__}: {exc}', seconds=time.monotonic() - started_at)
                        raise
                    else:
                        self.event('transport_branch_returned', branch=name, seconds=time.monotonic() - started_at)
                        return result
                    finally:
                        capture_context.transport_attempt, capture_context.physical = previous
                return wrapped
            return decorate

        def install(self):
            def merged(original):
                @functools.wraps(original)
                def wrapped(payload, *args, **kwargs):
                    self.event('merged_payload', payload=copy.deepcopy(payload))
                    return original(payload, *args, **kwargs)
                return wrapped

            def request(original):
                @functools.wraps(original)
                def wrapped(connection, method, url, body=None, headers={}, *, encode_chunked=False):
                    if getattr(capture_context, 'logical', None) is None:
                        return original(connection, method, url, body=body, headers=headers, encode_chunked=encode_chunked)
                    capture_context.physical = self.next_id('http')
                    started_at = time.monotonic()
                    self.event('send_started', method=method, url=url, host=connection.host, port=connection.port,
                        body_base64=base64.b64encode(body).decode('ascii') if isinstance(body, bytes) else None,
                        body_type=type(body).__name__, headers=dict(headers), encode_chunked=encode_chunked)
                    try:
                        result = original(connection, method, url, body=body, headers=headers, encode_chunked=encode_chunked)
                    except BaseException as exc:
                        self.event('send_failed', error=f'{type(exc).__name__}: {exc}', seconds=time.monotonic() - started_at)
                        raise
                    self.event('send_returned', seconds=time.monotonic() - started_at)
                    return result
                return wrapped

            def getresponse(original):
                @functools.wraps(original)
                def wrapped(connection, *args, **kwargs):
                    if getattr(capture_context, 'logical', None) is None:
                        return original(connection, *args, **kwargs)
                    started_at = time.monotonic()
                    try:
                        response = original(connection, *args, **kwargs)
                    except BaseException as exc:
                        self.event('getresponse_failed', error=f'{type(exc).__name__}: {exc}', seconds=time.monotonic() - started_at)
                        raise
                    with capture_lock:
                        self.responses[response] = (capture_context.logical,
                            getattr(capture_context, 'transport_attempt', None), getattr(capture_context, 'physical', None))
                    self.event('response_headers', status=response.status, reason=response.reason,
                        headers=list(response.headers.items()), seconds=time.monotonic() - started_at)
                    return response
                return wrapped

            def response_read(original):
                @functools.wraps(original)
                def wrapped(response, *args, **kwargs):
                    with capture_lock:
                        identity = self.responses.get(response)
                    if identity is None:
                        return original(response, *args, **kwargs)
                    previous = (getattr(capture_context, 'logical', None), getattr(capture_context, 'transport_attempt', None), getattr(capture_context, 'physical', None))
                    capture_context.logical, capture_context.transport_attempt, capture_context.physical = identity
                    started_at = time.monotonic()
                    try:
                        data = original(response, *args, **kwargs)
                    except BaseException as exc:
                        partial = getattr(exc, 'partial', None)
                        self.event('response_read_failed', error=f'{type(exc).__name__}: {exc}',
                            partial_base64=base64.b64encode(partial).decode('ascii') if isinstance(partial, bytes) else None,
                            seconds=time.monotonic() - started_at)
                        raise
                    else:
                        self.event('response_read_returned', body_base64=base64.b64encode(data).decode('ascii'), seconds=time.monotonic() - started_at)
                        return data
                    finally:
                        capture_context.logical, capture_context.transport_attempt, capture_context.physical = previous
                return wrapped

            self.patch(llm_module, 'post_chat_completion', merged)
            self.patch(transport, '_post_pooled', self.branch('pooled'))
            self.patch(transport, '_post_cancellable', self.branch('cancellable'))
            self.patch(urllib.request, 'urlopen', self.branch('urlopen'))
            self.patch(http.client.HTTPConnection, 'request', request)
            self.patch(http.client.HTTPConnection, 'getresponse', getresponse)
            self.patch(http.client.HTTPResponse, 'read', response_read)

        def restore(self):
            for owner, name, original in reversed(self.patches):
                setattr(owner, name, original)
            self.patches.clear()

    class Client(LlmRuntime):
        case_id = None

        def _post(self, payload, *post_args, **kwargs):
            case_id = self.case_id
            attempt = attempts.get(case_id, 0) + 1
            attempts[case_id] = attempt
            logical_post_id = f'{case_id}:{attempt}'
            before = time.monotonic()
            append('posts.jsonl', {'id': case_id, 'attempt': attempt, 'logical_post_id': logical_post_id, 'state': 'started', 'utc': utc(), 'payload': copy.deepcopy(payload)})
            previous_logical = getattr(capture_context, 'logical', None)
            capture_context.logical = logical_post_id
            try:
                response = super()._post(payload, *post_args, **kwargs)
            except Exception as exc:
                append('posts.jsonl', {'id': case_id, 'attempt': attempt, 'state': 'failed', 'error': f'{type(exc).__name__}: {exc}', 'seconds': time.monotonic() - before})
                raise
            finally:
                capture_context.logical = previous_logical
            record = {'id': case_id, 'attempt': attempt, 'state': 'returned', 'response': response, 'seconds': time.monotonic() - before}
            append('posts.jsonl', record)
            try:
                with urllib.request.urlopen(self._endpoint + '/slots', timeout=2) as stream:
                    append('slots.jsonl', {'id': case_id, 'attempt': attempt, 'slots': json.load(stream)})
            except Exception as exc:
                append('slots.jsonl', {'id': case_id, 'attempt': attempt, 'error': str(exc)})
            return response

    attempts = {}
    os.chdir(Path(config['python']).parent)
    client = Client()
    command = client._server_command()
    require(normalized_command(command) == normalized_command(previous_command), 'Inherited server command changed')
    prereg = {'utc': utc(), 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'candidate': 'OBSERVATION829/UNICODE_RETRY2', 'case_ids': [c['id'] for c in cases], 'case_count': 8,
        'own_invocation_pids': sorted(own_pids),
        'seals': seals, 'source_pins': pins, 'sources': sources, 'environment': environment, 'config': config,
        'server_command': command, 'previous772_server_command': previous_command, 'server_cwd': str(Path(config['python']).parent),
        'intent': 'status', 'input': 'Literal user_message; situation(kind=operation, operation=ocr.read, verified=true, succeeded=true, polarity=success, observed=unchanged receipt.Result). No other facts.',
        'budget': {'per_request_seconds': 4, 'warmup_seconds': 90, 'wall_seconds': 600, 'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768},
        'capture_scope': 'Every logical _post plus post-system-merge payload; every existing HTTP transport branch/physical request, exact body bytes in base64, response status/headers/read bytes/errors and timings. Temporary wrappers delegate once, never consume additional reads, and restore original functions. Transport retries and timeout arguments unchanged; logging has unavoidable timing overhead.',
        'method': 'One compose_user_message call per independent case; native BAXY retries unchanged; no parser or adjudicator.',
        'coverage_added': 0, 'quality_adjudicated': False, 'excluded': plan['excluded_credit']}
    write(OUT / 'PREREG.json', prereg)
    gpu, ram = ProcessTreeGpuSampler(os.getpid()), RamSampler(os.getpid())
    stop = threading.Event()
    violations, replies = [], []
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
    wire_capture = WireCapture()
    seals_unchanged = False
    try:
        require(check_seals(), 'Pre-inference seals changed')
        wire_capture.install()
        gpu.start()
        ram.start()
        watcher.start()
        client.start_warmup()
        require(client.wait_warmup(90), 'Warmup failed')
        require(normalized_command(client._server_command()) == normalized_command(previous_command), 'Effective command changed')
        write(OUT / 'READY.json', {'utc': utc(), 'runner': os.getpid(), 'server_pid': client._process.pid, 'server_command': client._server_command(), 'same772_command_except_port': True})
        for case in cases:
            require(not violations, 'Resource guard stopped run')
            require(check_seals(), 'Inter-case seals changed')
            client.case_id = case['id']
            facts = {'situation': {'kind': 'operation', 'operation': 'ocr.read', 'verified': True, 'succeeded': True, 'polarity': 'success', 'observed': copy.deepcopy(observed)}}
            append('inputs.jsonl', {'id': case['id'], 'user_message': case['user_message'], 'intent': 'status', 'facts': facts})
            answer, error = None, None
            case_started = time.monotonic()
            client.begin_request(4)
            try:
                answer = client.compose_user_message(case['user_message'], 'status', facts)
            except Exception as exc:
                error = f'{type(exc).__name__}: {exc}'
            finally:
                client.end_request()
            row = {'id': case['id'], 'answer': answer, 'error': error, 'attempts': attempts.get(case['id'], 0), 'seconds': time.monotonic() - case_started, 'request_budget_seconds': 4}
            replies.append(row)
            append('replies.jsonl', row)
            print(json.dumps({'completed': len(replies), 'registered': 8}), flush=True)
    except Exception as exc:
        fatal = f'{type(exc).__name__}: {exc}'
        append('fatal.jsonl', {'utc': utc(), 'error': fatal})
    finally:
        try:
            client.close()
        finally:
            wire_capture.restore()
        stop.set()
        if watcher.ident is not None:
            watcher.join(timeout=5)
        gpu.stop()
        ram.stop()
        try:
            seals_unchanged = check_seals()
        except Exception as exc:
            append('fatal.jsonl', {'utc': utc(), 'stage': 'final_seals', 'error': f'{type(exc).__name__}: {exc}'})
        result = {'utc': utc(), 'cases_completed': len(replies), 'cases_registered': 8, 'fatal_recorded': fatal is not None,
            'violations': violations, 'seconds': time.monotonic() - started, 'gpu_peak_mib': gpu.peak_mib,
            'gpu_telemetry_available': gpu.telemetry_available, 'ram_peak_mib': ram.peak_mib,
            'seals_unchanged': seals_unchanged, 'error_cases': sum(r['error'] is not None for r in replies),
            'quality_adjudicated': False, 'coverage_added': 0,
            'private_receipts': {p.name: sha(p) for p in PRIVATE.iterdir() if p.is_file()}}
        write(OUT / 'RESULT.json', result)
        print(json.dumps(result), flush=True)
    return 0 if fatal is None and not violations and seals_unchanged and len(replies) == 8 and not any(r['error'] for r in replies) else 1


if __name__ == '__main__':
    raise SystemExit(main())
