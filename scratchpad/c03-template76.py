from pathlib import Path
import copy
import hashlib
import io
import json
import os
import sys
import time
import urllib.error

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / 'src'), str(root)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

sys.stdout.reconfigure(encoding='utf-8')
variant_model = sys.argv[1]
assert variant_model in {'qwen35', 'registered'}
base = root / 'artifacts/comprobaciones/C03'
out = base / ('astra-template76-' + variant_model)
out.mkdir(exist_ok=False)
wire_path = base / 'astra-files75-http/wire-36724.jsonl'
wire = [json.loads(s) for s in wire_path.read_text(encoding='utf-8').splitlines()]
cases = []
seen = set()
for row in wire:
    if not row.get('httpError'):
        continue
    signature = json.dumps(row['payload'], sort_keys=True)
    if signature not in seen:
        seen.add(signature)
        cases.append((f'error{len(cases) + 1}', row['payload']))
cases.append(('selector_control', next(row['payload'] for row in wire if row['payload'].get('tool_choice') == 'auto')))
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
model = Path(config['gguf'] if variant_model == 'registered' else 'D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
with model.open('rb') as stream:
    model_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
prereg = {'method': 'Exact unique HTTP400 payloads75 and one successful native selector control. '
    'Compare captured messages with only trusted system messages joined in original order at position0. '
    'Preserve all non-system messages byte-for-byte/in order; no instruction removal, current request rewrite, '
    'model setting change, functions executed, UI/audio or human reserve. Native replay, not product acceptance. '
    'Qwen3.5 official template rejects every system message except first; registered2507 is compatibility control.',
    'source': 'https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/chat_template.jinja',
    'sourceConsulted': '2026-09-07', 'model': str(model), 'modelSha256': model_sha,
    'wireSha256': hashlib.sha256(wire_path.read_bytes()).hexdigest(),
    'sourceSha256': hashlib.sha256((root / 'src/baxy_mind/llm.py').read_bytes()).hexdigest(),
    'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest(), 'cases': [ident for ident, _ in cases]}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid()); ram = RamSampler(os.getpid())
gpu.start(); ram.start(); started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    (out / 'llama-command.json').write_text(json.dumps(client._server_command(), indent=2), encoding='utf-8')
    for ident, original in cases:
        for variant in ('captured', 'one_system'):
            payload = copy.deepcopy(original)
            if variant == 'one_system':
                systems = [m['content'] for m in payload['messages'] if m['role'] == 'system']
                assert all(isinstance(s, str) for s in systems)
                payload['messages'] = ([{'role': 'system', 'content': '\n\n'.join(systems)}] if systems else []) + [m for m in payload['messages'] if m['role'] != 'system']
            row = {'id': ident, 'variant': variant, 'payload': payload}
            client.begin_request(40)
            try:
                row['response'] = client._post(payload)
            except urllib.error.HTTPError as error:
                row['httpError'] = {'code': error.code, 'body': error.fp.getvalue().decode('utf-8') if isinstance(error.fp, io.BytesIO) else error.read().decode('utf-8')}
            finally:
                client.end_request()
            with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            choice = row.get('response', {}).get('choices', [{}])[0]
            print(json.dumps({'id': ident, 'variant': variant, 'error': row.get('httpError', {}).get('code'),
                'finish': choice.get('finish_reason'), 'message': choice.get('message')}, ensure_ascii=False), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
              'ramPeakMiB': ram.peak_mib, 'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
