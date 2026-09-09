"""Measure post-stable backend with exact existing profile/input controls."""
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
out = base / 'astra-nightly-inference456'
private = local / 'C03-nightly-inference456-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
with (local / 'C03-memory-gemma444-private/posts.jsonl').open(encoding='utf-8-sig') as f:
    cases = [{'id': r['id'], 'payload': r['payload']} for r in map(json.loads, f)]
assert len(cases) == 11 and len({c['id'] for c in cases}) == 11
models = {
    'qwen35-4b': Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf'),
    'gemma-published': Path('D:/BAXYRuntime/experiments/models/baxy-gemma4-e2b-published-f9b84ecd/gemma-4-E2B-it-Q4_K_M.gguf'),
}
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

profiles = {
    'qwen35-4b': {'temperature': .7, 'top_p': .8, 'top_k': 20, 'min_p': 0., 'presence_penalty': 1.5, 'repeat_penalty': 1.},
    'gemma-published': {'temperature': 1., 'top_p': .95, 'top_k': 64, 'min_p': 0., 'presence_penalty': 0., 'repeat_penalty': 1.},
}
seeds = [0, 17, 4294967295]
variants = {'qwen35-4b': [('greedy', None), ('documented', 0), ('documented', 17)], 'gemma-published': [('greedy', None)]}
initial = sha(manifest)
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'After454/455, compare exact existing inputs/profiles with b10865. Qwen3.5:11 unchanged T0 payloads450 plus22 documented nonthinking payloads451/seeds0,17. PublishedGemma:11 unchanged T0 controls450 (GDN fix does not target its architecture). New backend includes GDN correction28068 and CUDA changes; not isolated attribution to one commit. No model/source/prompt/quantization/context/profile changes. Direct loopback HTTP single attempt avoids transport retries; one system prefix unchanged. First template render and server props saved. No promotion/UI/voice/fresh acceptance.',
    'evidence': ['https://huggingface.co/Qwen/Qwen3.5-4B', 'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507', 'https://huggingface.co/google/gemma-4-E2B-it', 'https://huggingface.co/google/gemma-4-E2B-it/blob/main/generation_config.json', 'https://arxiv.org/html/2607.02770v1', 'https://github.com/ggml-org/llama.cpp/discussions/27115', 'https://github.com/ggml-org/llama.cpp/blob/5266f24da/tools/server/README.md'],
    'profiles': profiles,
    'seeds': seeds,
    'budget_reason': 'OriginalT0 max256; documented max1024, matching450/451 exactly. Previous matching profiles had no length cutoff or timeout. Direct HTTP60s one attempt; length/timeouts remain censored.',
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
                    write(private / (key + route.replace('/', '-') + '.json'), json.load(reply))
            for variant, seed, case in [(v, seed, case) for v, seed in variants[model_name] for case in cases]:
                payload = copy.deepcopy(case['payload'])
                if variant == 'documented':
                    payload.update(profiles[model_name], seed=seed, max_tokens=1024)
                else:
                    assert payload == case['payload']
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
        assert completed == 11 * len(variants[model_name]) and not violations
assert sha(manifest) == initial
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
