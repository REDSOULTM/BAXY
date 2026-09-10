"""Observe K2 loading, template, reasoning and JSON on the isolated CUDA backend."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
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

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

parser = argparse.ArgumentParser()
parser.add_argument('--variant', default='0.9B-Q8_0')
parser.add_argument('--tag', default='q8-auto')
parser.add_argument('--pure-content', action='store_true')
parser.add_argument('--panel', action='store_true', help='Run the frozen50-case comparison after backend smoke succeeds.')
parser.add_argument('--neutral-panel', action='store_true', help='Run independent synthetic699 tasks without any BAXY instructions.')
parser.add_argument('--selector-ablation', action='store_true', help='Run paired700 selectors with only their existing system policy removed.')
parser.add_argument('--family', choices=['k2', 'qwen'], default='k2')
parser.add_argument('--qwen-backend', choices=['registered', 'ifm'], default='registered')
parser.add_argument('--sampling', choices=['recommended', 'registered'], default='recommended')
parser.add_argument('--ctx-size', type=int, default=36864)
parser.add_argument('--max-tokens', type=int, default=32768)
parser.add_argument('--gpu-layers', type=int, default=99)
parser.add_argument('--no-kv-offload', action='store_true')
parser.add_argument('--no-mmap', action='store_true')
parser.add_argument('--cache-type', choices=['q8_0', 'f16'], default='q8_0')
parser.add_argument('--tool-format', choices=['json', 'native'], default='json')
parser.add_argument('--selectors-only', action='store_true')
parser.add_argument('--no-op-offload', action='store_true')
parser.add_argument('--effort', choices=['high', 'medium', 'low'], default='high')
parser.add_argument('--observe-template', action='store_true', help='Pin the rendered generation prefix without running inference.')
args = parser.parse_args()
assert not (args.panel and args.neutral_panel), 'Choose exactly one panel kind'
assert not args.selector_ablation or (not args.panel and not args.neutral_panel and not args.selectors_only and args.sampling == 'recommended')
assert not args.neutral_panel or (args.sampling == 'recommended' and not args.selectors_only and not args.pure_content)
base = root / 'artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696'
if args.neutral_panel:
    base = root / 'artifacts/comprobaciones/C03/K2_HORIZON_NATIVE699'
if args.selector_ablation:
    base = root / 'artifacts/comprobaciones/C03/K2_HORIZON_SELECTOR700'
out = base / (('run-' if args.panel or args.neutral_panel or args.selector_ablation else 'smoke-') + args.tag)
out.mkdir(parents=True, exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / ('BAXY/C03-k2-' + ('ablation700-' if args.selector_ablation else 'native699-' if args.neutral_panel else 'run696-' if args.panel else 'smoke696-') + args.tag + '-private')
private.mkdir(parents=True, exist_ok=False)
binary = Path('D:/BAXYRuntime/build/llama-k2-horizon-35999d1/build-cuda13-sm86/bin/llama-server.exe')
model = Path('D:/BAXYRuntime/experiments/models/k2-horizon-20260909') / ('K2-Horizon-' + args.variant + '.gguf')
if args.family == 'qwen':
    if args.qwen_backend == 'registered':
        binary = Path('D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe')
    model = Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf')
assert binary.is_file() and model.is_file()
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def append(path, data):
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(data, ensure_ascii=False) + '\n')

manifest_hash = sha(manifest)
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
command = [str(binary), '-m', str(model), '--host', '127.0.0.1', '--port', str(port),
           '--ctx-size', str(args.ctx_size), '--parallel', '1', '-ngl', str(args.gpu_layers), '-b', '512', '-ub', '128',
           '--flash-attn', 'on', '--cache-type-k', args.cache_type, '--cache-type-v', args.cache_type,
           '--fit', 'off', '--cache-ram', '0', '--jinja', '--reasoning', 'on',
           '--reasoning-effort', args.effort, '--reasoning-budget', '-1',
           '--reasoning-format', 'none' if args.pure_content else 'deepseek']
if args.pure_content:
    command.append('--skip-chat-parsing')
if args.no_kv_offload:
    command.append('--no-kv-offload')
if args.no_mmap:
    command.append('--no-mmap')
if args.no_op_offload:
    command.append('--no-op-offload')
if args.observe_template and args.family == 'k2':
    command += ['--verbosity', '3']
if args.family == 'qwen':
    source = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-observe-identity593-private/effective-server-command.json'
    command = json.loads(source.read_text(encoding='utf-8-sig'))
    command[0] = str(binary)
    command[command.index('--port') + 1] = str(port)
    command[command.index('--log-file') + 1] = str(private / 'server.log')
    if args.sampling != 'registered':
        for flag, value in [('-c', args.ctx_size), ('-np', 1), ('-b', 512), ('-ub', 128), ('-ngl', args.gpu_layers)]:
            command[command.index(flag) + 1] = str(value)
        if args.no_kv_offload:
            command.append('--no-kv-offload')
schema = {'type': 'object', 'properties': {'operation': {'type': 'string', 'enum': ['audio.status']},
          'arguments': {'type': 'object', 'properties': {}, 'additionalProperties': False}},
          'required': ['operation', 'arguments'], 'additionalProperties': False}
cases = [
    {'case': 'spanish-facts', 'messages': [
        {'role': 'system', 'content': 'Eres BAXY. Responde al usuario brevemente en español usando sólo los datos observados. No inventes acciones.'},
        {'role': 'user', 'content': '¿Cuánta RAM queda libre? Datos verificados: RAM instalada 16 GiB; utilizable 15 GiB; libre 4 GiB; usada 11 GiB.'}]},
    {'case': 'english-schema', 'messages': [
        {'role': 'system', 'content': 'Propose the requested read-only operation from this catalog: audio.status takes an empty arguments object. Do not claim an execution. Return the JSON object.'},
        {'role': 'user', 'content': 'What is the current system volume?'}],
     'response_format': {'type': 'json_schema', 'json_schema': {'name': 'operation', 'strict': True, 'schema': schema}}},
    {'case': 'english-tool', 'messages': [{'role': 'user', 'content': 'What is the current system volume?'}],
     'tools': [{'type': 'function', 'function': {'name': 'audio_status', 'description': 'Read the current system volume.',
        'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}}}], 'tool_choice': 'auto'},
]
panel_hash = None
if args.panel:
    panel_path = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-k2-comparison696-private/panel.json'
    panel_hash = sha(panel_path)
    assert panel_hash == '5a5aa1d46bbc60eb757566ac535c89ebf0755f4da7ed4f03b7215241787cea76'
    frozen = json.loads(panel_path.read_text(encoding='utf-8'))
    cases = [{'case': row['id'], **row['payload']} for row in frozen]
    assert len(cases) == 50
    if args.selectors_only:
        cases = [case for case in cases if case['case'].startswith('select-')]
        assert len(cases) == 20
if args.neutral_panel:
    panel_path = base / 'PANEL.json'
    panel_hash = sha(panel_path)
    assert panel_hash == 'a29167820a7a40ca2c43571276d98596ab0e146eb6b82ac699f768b85a035443'
    frozen = json.loads(panel_path.read_text(encoding='utf-8'))
    assert len(frozen) == 50
    assert all(set(row['payload']) == {'messages'} for row in frozen)
    assert all(m['role'] in {'user', 'assistant'} for row in frozen for m in row['payload']['messages'])
    cases = [{'case': row['id'], **row['payload']} for row in frozen]
ablation_reference = None
if args.selector_ablation:
    plan = json.loads((base/'PLAN.json').read_text(encoding='utf-8'))
    preparation = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-selector-ablation700-private'
    panel_path = preparation/'panel.json'
    panel_hash = sha(panel_path)
    assert panel_hash == plan['panel_sha256'] == '5c1f96a678c04c3f42cc7aeca752df31c10f63a6954cb6383c8e296a4c531b0c'
    frozen = json.loads(panel_path.read_text(encoding='utf-8'))
    cases = [{'case': row['id'], **row['payload']} for row in frozen]
    assert len(cases) == 20 and [c['case'] for c in cases] == plan['case_ids']
    paired = plan['baselines'][args.family]
    assert sha(root/paired['preregistration_path']) == paired['preregistration_sha256']
    previous = json.loads((root/paired['preregistration_path']).read_text(encoding='utf-8'))
    assert sha(model) == previous['model_sha256'] and sha(binary) == previous['binary_sha256']
    assert {p.name: sha(p) for p in sorted(binary.parent.iterdir()) if p.suffix in ['.exe','.dll']} == previous['backend_files']
    def normalized(cmd):
        values = list(cmd)
        for flag in ['--port','--log-file']:
            if flag in values:
                values[values.index(flag)+1] = '<dynamic-local-value>'
        return values
    assert normalized(command) == normalized(previous['command']), 'Paired server configuration changed'
    expected_path = preparation/(args.family+'-expected-requests.json')
    assert sha(expected_path) == paired['expected_requests_sha256']
    ablation_reference = {r['case']:r['payload'] for r in json.loads(expected_path.read_text(encoding='utf-8'))}
    write(out/'PAIRED_BASELINE.json', {'baseline':paired['tag'],'preregistration_sha256':paired['preregistration_sha256'],
        'command_equal_except_port_and_log':True,'backend_and_model_equal':True,'cases':20,
        'removed_system_sha256':plan['removed_system_sha256']})
(private / 'driver.py').write_bytes(Path(__file__).read_bytes())
(private / 'tokenizer_parity_driver.py').write_bytes(Path(__file__).with_name('c03_k2_tokenizer_parity696.py').read_bytes())
write(out / 'PREREG.json', {'utc': datetime.now(timezone.utc).isoformat(), 'command': command,
    'driver_sha256': sha(Path(__file__)),
    'backend_files': {p.name: sha(p) for p in sorted(binary.parent.iterdir()) if p.suffix in ['.exe', '.dll']},
    'tokenizer_parity_driver_sha256': sha(Path(__file__).with_name('c03_k2_tokenizer_parity696.py')),
    'model_sha256': sha(model), 'binary_sha256': sha(binary), 'manifest_sha256': manifest_hash,
    'cases': [case['case'] for case in cases], 'panel_sha256': panel_hash, 'arguments': vars(args),
    'executed_case_count': len(cases),
    'case_selection': 'Complete selector category from the frozen50 panel' if args.selectors_only else 'All configured cases',
    'method': ('Paired700 selector-policy ablation: only the first system message removed, all other effective fields and normalized server configuration asserted identical to historical per-model controls. Catalog/history remain conditioned on BAXY. No effects.' if args.selector_ablation else 'Independent699: same50 synthetic tasks, only user/assistant messages. No BAXY system/catalog/rules, tools, schema or execution. Official embedded template and documented model-specific sampling; context/output caps explicit. Only reference profiles carry full manufacturer output headroom; practical profiles are labeled separately. Not C03 acceptance.' if args.neutral_panel else 'Frozen50 native shared inputs with BAXY instructions, no BAXY guard or provider execution. Documented model-specific sampling and template, with geometry explicit; all omissions/errors retained. No model promotion from native replay alone.' if args.panel else 'Backend diagnostic only, no model ranking. Observe template/reasoning/schema/tool-call handling before BAXY comparison. No effects executed.'),
    'limits': {'gpu_mib': 3800, 'minimum_free_ram_mib': 768, 'request_seconds': 900}})
environment = os.environ.copy()
environment['PATH'] = 'C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v13.0/bin;' + environment['PATH']
with (private / 'launch.log').open('w', encoding='utf-8') as launch:
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=launch, stderr=subprocess.STDOUT,
        cwd=binary.parent, env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
write(out / 'PROCESS.json', {'pid': process.pid, 'command': command})
gpu = ProcessTreeGpuSampler(process.pid)
ram = RamSampler(process.pid)
gpu.start()
ram.start()
stop = threading.Event()
violations = []
started = time.monotonic()

def terminate():
    if process.poll() is None:
        process.terminate()

def guard():
    while not stop.wait(.25):
        if (gpu.peak_mib or 0) > 3800:
            violations.append('gpu_limit')
        if psutil.virtual_memory().available < 768 * 2**20:
            violations.append('free_ram_limit')
        if violations:
            terminate()
            return

thread = threading.Thread(target=guard, daemon=True)
thread.start()
url = f'http://127.0.0.1:{port}'
try:
    while time.monotonic() - started < 120:
        if process.poll() is not None:
            raise RuntimeError(f'backend exited before readiness: {process.returncode}')
        try:
            with urllib.request.urlopen(url + '/health', timeout=2) as response:
                health = json.load(response)
            if health.get('status') == 'ok':
                break
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(.25)
    else:
        raise TimeoutError('backend startup')
    with urllib.request.urlopen(url + '/props', timeout=10) as response:
        write(private / 'props.json', json.load(response))
    write(out / 'READY.json', {'seconds': time.monotonic() - started})
    if args.family == 'k2':
        from c03_k2_tokenizer_parity696 import verify
        parity = verify(url, '3.7B' if args.variant.startswith('3.7B') else '0.9B', private)
        write(out / 'TOKENIZER_PARITY.json', parity)
    for case in cases:
        payload = {k: v for k, v in case.items() if k != 'case'}
        if args.sampling == 'recommended':
            is_k2 = args.family == 'k2'
            temperature = (1.0 if args.variant.startswith('3.7B') else .6) if is_k2 else .7
            payload.update(temperature=temperature, top_p=.95 if is_k2 else .8, top_k=0 if is_k2 else 20,
                min_p=0.0, repeat_penalty=1.0, presence_penalty=0.0, seed=0, max_tokens=args.max_tokens)
            payload['chat_template_kwargs'] = ({'enable_thinking': True, 'reasoning_effort': args.effort,
                'tool_presentation_format': 'json', 'tool_call_format': 'json'} if is_k2 else {'enable_thinking': False})
            if is_k2 and args.tool_format == 'native':
                payload['chat_template_kwargs'].pop('tool_presentation_format')
                payload['chat_template_kwargs'].pop('tool_call_format')
            if args.neutral_panel:
                # Manufacturer user-only recipe: no BAXY or unnecessary Qwen thinking override.
                if is_k2:
                    payload['chat_template_kwargs'] = {'reasoning_effort': args.effort}
                else:
                    payload.pop('chat_template_kwargs', None)
        payload.update(stream=True, stream_options={'include_usage': True}, cache_prompt=False)
        if ablation_reference is not None:
            assert payload == ablation_reference[case['case']], 'Paired payload changed outside removed system'
            append(out/'PAYLOAD_PARITY.jsonl', {'case':case['case'],'equal_except_removed_system':True})
        append(private / 'requests.jsonl', {'case': case['case'], 'payload': payload})
        if args.observe_template and (args.family == 'k2' or args.neutral_panel):
            template_request = urllib.request.Request(url + '/apply-template',
                data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(template_request, timeout=30) as rendered_response:
                rendered = json.load(rendered_response)['prompt']
            append(private / 'rendered-prompts.jsonl', {'case': case['case'], 'prompt': rendered})
            expected_prefix = ({'high': '<ifm|think>', 'medium': '<ifm|think_fast>', 'low': '<ifm|think_faster>'}[args.effort]
                if args.family == 'k2' else '<|im_start|>assistant')
            assert rendered.rstrip().endswith(expected_prefix), 'Effective template effort mismatch'
            if args.neutral_panel:
                assert 'BAXY' not in rendered.upper(), 'Unexpected BAXY injection in native template'
            append(out / 'TEMPLATE_PARITY.jsonl', {'case': case['case'], 'effort': args.effort,
                'suffix_matches': True, 'prompt_sha256': hashlib.sha256(rendered.encode()).hexdigest()})
        before = time.monotonic()
        record = {'case': case['case'], 'content': '', 'reasoning_content': '', 'tool_deltas': []}
        request = urllib.request.Request(url + '/v1/chat/completions', data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                for line in response:
                    if time.monotonic() - before > 900:
                        record['error'] = 'request_wall_clock_deadline_900_seconds'
                        break
                    if not line.startswith(b'data: '):
                        continue
                    data = line[6:].strip()
                    if data == b'[DONE]':
                        break
                    event = json.loads(data)
                    append(private / 'stream.jsonl', {'case': case['case'], 'seconds': time.monotonic()-before, 'event': event})
                    if event.get('error'):
                        record['error'] = event['error']
                    if event.get('usage'):
                        record['usage'] = event['usage']
                    for choice in event.get('choices', []):
                        delta = choice.get('delta', {})
                        if any(delta.get(k) for k in ['content', 'reasoning_content', 'tool_calls']):
                            record.setdefault('first_token_seconds', time.monotonic() - before)
                        if delta.get('content'):
                            record.setdefault('first_content_seconds', time.monotonic() - before)
                        for key in ['content', 'reasoning_content']:
                            record[key] += delta.get(key) or ''
                        if delta.get('tool_calls'):
                            record['tool_deltas'].extend(delta['tool_calls'])
                        if choice.get('finish_reason'):
                            record['finish_reason'] = choice['finish_reason']
        except Exception as error:
            record['error'] = str(error)
            if isinstance(error, urllib.error.HTTPError):
                record['body'] = error.read().decode(errors='replace')
        record['seconds'] = time.monotonic() - before
        append(private / 'results.jsonl', record)
        print(json.dumps({k: v for k, v in record.items() if k != 'reasoning_content'} | {
            'reasoning_characters': len(record['reasoning_content'])}, ensure_ascii=False), flush=True)
        assert not violations
finally:
    stop.set()
    terminate()
    process.wait(timeout=20)
    thread.join(timeout=2)
    gpu.stop()
    ram.stop()
    write(out / 'RESOURCES.json', {'gpu_peak_mib': gpu.peak_mib, 'ram_peak_mib': ram.peak_mib,
        'seconds': time.monotonic() - started, 'violations': violations,
        'manifest_unchanged': sha(manifest) == manifest_hash, 'backend_exit': process.returncode})
