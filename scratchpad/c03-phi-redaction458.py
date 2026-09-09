"""Test typed protected records only after Phi first solved the normal names."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import sys
import threading
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'src')]
import psutil
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = base / 'astra-phi-redaction458'
private = local / 'C03-phi-redaction458-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
with (local / 'C03-memory-gemma444-private/posts.jsonl').open(encoding='utf-8-sig') as f:
    cases = [{'id': r['id'], 'payload': r['payload']} for r in map(json.loads, f)]
assert len(cases) == 11 and len({c['id'] for c in cases}) == 11
models = {'phi4-mini': Path('D:/BAXYRuntime/experiments/models/phi4-mini-7ff82c2a/microsoft_Phi-4-mini-instruct-Q4_K_M.gguf')}
servers = {
    'b10865': Path('D:/BAXYRuntime/assets/llama-b10865-cuda12.4/llama-server.exe'),
}
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

def append(path, value):
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False) + '\n')

profiles = {'phi4-mini': {'temperature': 0., 'top_p': 1., 'top_k': 0, 'min_p': 0., 'presence_penalty': 0., 'repeat_penalty': 1.}}
seeds = [0]
variants = {'phi4-mini': [('documented', 0)]}
assert sha(models['phi4-mini']) == '01999f17c39cc3074afae5e9c539bc82d45f2dd7faa3917c66cbef76fce8c0c2'
initial = sha(manifest)
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Fourteen native completions: eleven unchanged457 baselines plus three protected/mixed cases with only observed records representation changed from value[REDACTED] to omitted value/redacted:true. OfficialPhi greedy500, exact template, b10865, inputs and all other fields unchanged.443Qwen and446publishedGemma found no gain with this representation; preserve those rejections. New measured evidence457: a different candidate Phi natively solves all8 normal memory controls and the mixed record, but fails the two all-protected cases. One bounded check of whether representation is the remaining cause; no source adoption or further wording variants if no gain. No claims that arbitrary records belong to the user.',
    'evidence': ['https://huggingface.co/microsoft/Phi-4-mini-instruct', 'https://huggingface.co/microsoft/Phi-4-mini-instruct/blob/main/generation_config.json', 'https://huggingface.co/microsoft/Phi-4-mini-instruct/blob/main/tokenizer_config.json', 'https://arxiv.org/abs/2503.01743', 'artifacts/research/phi4_mini_candidate_verdict_20260811.json', 'documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md:4042'],
    'profiles': profiles,
    'seeds': seeds,
    'budget_reason': 'Official example max500 and non-thinking. Any length/timeout is censored. Same4096/slot x3 and GPU watchdog3800MiB. Native measured predictions are not product acceptance.',
    'criteria': 'Review all answers, finish reasons, usage and resources. Correct speaker, values and protected-record handling without fabricated tools/effects. An exchange of failures is not success. No runtime promotion on this native diagnostic. No physical UI/audio/fresh acceptance credit.',
    'models': {k: {'path': str(p), 'sha256': sha(p)} for k, p in models.items()},
    'servers': {k: {'path': str(p), 'sha256': sha(p)} for k, p in servers.items()},
    'cases': [{'id': c['id'], 'payload_sha256': hashlib.sha256(json.dumps(c['payload'], sort_keys=True, ensure_ascii=False).encode()).hexdigest()} for c in cases],
    'manifest_sha256': initial,
    'source_sha256': sha(root / 'src/baxy_mind/llm.py'),
    'limits': {'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768, 'request_seconds': 60},
    'private': str(private),
})
resources = []
for model_name, model in models.items():
    for backend, server in servers.items():
        key = model_name + '-' + backend
        for env_key in list(os.environ):
            if env_key.startswith('BAXY_MIND_'):
                os.environ.pop(env_key)
        os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=str(server), BAXY_MIND_NGL='99', BAXY_MIND_KV_CACHE_TYPE='q8_0')
        client = LlmRuntime()
        gpu = ProcessTreeGpuSampler(os.getpid())
        ram = RamSampler(os.getpid())
        stop = threading.Event()
        violations = []
        started = time.monotonic()
        completed = 0
        sampled_seeds = set()

        def watch():
            while not stop.wait(.25):
                if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
                    violations.append('gpu_bound')
                if psutil.virtual_memory().available < 768 * 2**20:
                    violations.append('system_free_ram_bound')
                if violations:
                    client.close()
                    return
                if len(sampled_seeds) < len(seeds) and client._endpoint:
                    try:
                        with urllib.request.urlopen(client._endpoint + '/slots', timeout=.3) as reply:
                            slots = json.load(reply)
                        for slot in slots:
                            params = slot.get('params', {})
                            sample_seed = params.get('seed')
                            if slot.get('is_processing') and sample_seed in seeds and sample_seed not in sampled_seeds:
                                append(private / 'effective-slots.jsonl', {'model': model_name, 'backend': backend, 'slot': slot})
                                sampled_seeds.add(sample_seed)
                    except (OSError, ValueError):
                        pass

        guard = threading.Thread(target=watch, daemon=True)
        try:
            gpu.start()
            ram.start()
            guard.start()
            client.start_warmup()
            assert client.wait_warmup(90)
            assert gpu.telemetry_available and gpu.peak_mib is not None
            write(out / (key + '-command.json'), client._server_command())
            for route, body in [('/props', None), ('/apply-template', cases[0]['payload'])]:
                request = urllib.request.Request(client._endpoint + route, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(request, timeout=15) as reply:
                    data = json.load(reply)
                    write(private / (key + route.replace('/', '-') + '.json'), data)
                    if route == '/apply-template':
                        expected = ''.join('<|' + m['role'] + '|>' + m['content'] + '<|end|>' for m in cases[0]['payload']['messages']) + '<|assistant|>'
                        assert data['prompt'] == expected, 'Phi native template differs from official no-tools rendering'
            pairs = [('documented', 0, case) for case in cases] + [('typed-redaction', 0, case) for case in cases if case['id'] in {'redacted-es', 'redacted-en', 'mixed-es'}]
            for variant, seed, case in pairs:
                payload = copy.deepcopy(case['payload'])
                if variant in {'documented', 'typed-redaction'}:
                    payload.update(profiles[model_name], seed=seed, max_tokens=500)
                else:
                    assert payload == case['payload']
                if variant == 'typed-redaction':
                    lines = payload['messages'][-1]['content'].splitlines()
                    for index, line in enumerate(lines):
                        if not line.startswith('situation: '):
                            continue
                        situation = json.loads(line.removeprefix('situation: '))
                        for record in situation['seen']['records']:
                            if record.get('value') == '[REDACTED]':
                                record.pop('value')
                                record['redacted'] = True
                        lines[index] = 'situation: ' + json.dumps(situation, ensure_ascii=False)
                    payload['messages'][-1]['content'] = '\n'.join(lines)
                before = time.monotonic()
                client.begin_request(60)
                row = {'model': model_name, 'backend': backend, 'id': case['id'], 'seed': seed, 'variant': variant}
                try:
                    request = urllib.request.Request(client._endpoint + '/v1/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(request, timeout=60) as reply:
                        response = json.load(reply)
                    choice = response['choices'][0]
                    row.update(answer=choice['message'].get('content'), reasoning=choice['message'].get('reasoning_content'), finish_reason=choice.get('finish_reason'), usage=response.get('usage'), timings=response.get('timings'))
                    append(private / 'posts.jsonl', {**row, 'payload': payload, 'response': response})
                    completed += 1
                except Exception as error:
                    row['error'] = type(error).__name__ + ': ' + str(error)
                finally:
                    client.end_request()
                row['seconds'] = round(time.monotonic() - before, 3)
                append(out / 'replies.jsonl', row)
                print(json.dumps({k: v for k, v in row.items() if k not in {'usage', 'timings', 'reasoning'}}, ensure_ascii=True), flush=True)
                if violations:
                    break
        finally:
            stop.set()
            client.close()
            guard.join(timeout=5)
            gpu.stop()
            ram.stop()
            resource = {'model': model_name, 'backend': backend, 'completed': completed, 'violations': violations, 'effective_seeds_observed': sorted(sampled_seeds), 'gpu_peak_mib': gpu.peak_mib, 'ram_peak_mib': ram.peak_mib, 'seconds': round(time.monotonic() - started, 3)}
            resources.append(resource)
            write(out / 'resources.json', resources)
            print(json.dumps(resource), flush=True)
        assert completed == 14 and not violations
assert sha(manifest) == initial
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
