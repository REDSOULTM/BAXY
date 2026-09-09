"""Measure documented non-thinking profiles; all preregistered seeds retained."""
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
out = base / 'astra-model-profiles451'
private = local / 'C03-model-profiles451-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
with (local / 'C03-memory-gemma444-private/posts.jsonl').open(encoding='utf-8-sig') as f:
    cases = [{'id': r['id'], 'payload': r['payload']} for r in map(json.loads, f)]
assert len(cases) == 11 and len({c['id'] for c in cases}) == 11
models = {
    'qwen35-4b': Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf'),
    'qwen2507': Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf'),
    'gemma-base': Path('D:/BAXYRuntime/experiments/models/gemma4-e2b-inherited-d3b0fed4/base-gguf/gemma-4-E2B-it-Q4_K_M.gguf'),
    'gemma-published': Path('D:/BAXYRuntime/experiments/models/baxy-gemma4-e2b-published-f9b84ecd/gemma-4-E2B-it-Q4_K_M.gguf'),
}
servers = {
    'b10809': Path('D:/BAXYRuntime/assets/llama-v0.4.0-b10809-cuda12.4/llama-server.exe'),
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
    'qwen2507': {'temperature': .7, 'top_p': .8, 'top_k': 20, 'min_p': 0., 'presence_penalty': 0., 'repeat_penalty': 1.},
    'gemma-base': {'temperature': 1., 'top_p': .95, 'top_k': 64, 'min_p': 0., 'presence_penalty': 0., 'repeat_penalty': 1.},
    'gemma-published': {'temperature': 1., 'top_p': .95, 'top_k': 64, 'min_p': 0., 'presence_penalty': 0., 'repeat_penalty': 1.},
}
seeds = [0, 17]
initial = sha(manifest)
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Four existing exact GGUFs on verified b10809; documented non-thinking profiles for brief verified-status composition. Same11 captured444 inputs and seeds0/17 fixed before inference, all22 answers per model counted (not best-of). Qwen3.5 general non-thinking T.7/p.8/k20/min0/presence1.5/repeat1;2507 T.7/p.8/k20/min0, optional presence left0; Gemma T1/p.95/k64 with min_p0 to avoid an additional undocumented llama default filter. Presence window remains backend default64, so no claim of full Transformers distribution parity. max_tokens1024, thinking off, same4096/slot x3,ngl99/KVq8/cache0/no-mmap. Contrast whole documented profile, not isolated sampler causality. No source edits, guarded retries, effects, registration or fresh acceptance.',
    'evidence': ['https://huggingface.co/Qwen/Qwen3.5-4B', 'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507', 'https://huggingface.co/google/gemma-4-E2B-it', 'https://huggingface.co/google/gemma-4-E2B-it/blob/main/generation_config.json', 'https://arxiv.org/html/2607.02770v1', 'https://github.com/ggml-org/llama.cpp/discussions/27115', 'https://github.com/ggml-org/llama.cpp/blob/5266f24da/tools/server/README.md'],
    'profiles': profiles,
    'seeds': seeds,
    'budget_reason': 'Actual450 completions all stopped naturally below256.1024 provides room for stochastic variation on brief non-thinking status tasks; any length/timeout outcome is reported as censored, never a semantic failure of a fully delivered response. Thinking needs its own budget and measurement if necessary.',
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
            for seed, case in [(seed, case) for seed in seeds for case in cases]:
                payload = copy.deepcopy(case['payload'])
                payload.update(profiles[model_name], seed=seed, max_tokens=1024)
                before = time.monotonic()
                client.begin_request(60)
                row = {'model': model_name, 'backend': backend, 'id': case['id'], 'seed': seed}
                try:
                    response = client._post(payload)
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
        assert completed == 22 and not violations
assert sha(manifest) == initial
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
