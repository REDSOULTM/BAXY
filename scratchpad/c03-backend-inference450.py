"""Isolate backend changes with the eleven fixed memory composition inputs."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import sys
import threading
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'src')]
import psutil
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = base / 'astra-backend-inference450'
private = local / 'C03-backend-inference450-private'
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
    'b9980': Path('D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe'),
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

initial = sha(manifest)
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Two models x two backends, sequential independent server instances, eleven unchanged native first completions per instance. Exact444 payloads, no changed prompts, model-specific template, T0, max256, thinking off, no reclassification or validation/retry. Compatibility449 established identical rendered prompts and context. This isolates backend behavior; it is explicitly not a fair overall model ranking. Documented model-specific sampling profiles must follow per owner20.',
    'criteria': 'Review all answers, finish reasons, usage and resources. Correct speaker, values and protected-record handling without fabricated tools/effects. An exchange of failures is not success. No runtime promotion on this native diagnostic. No physical UI/audio/fresh acceptance credit.',
    'models': {k: {'path': str(p), 'sha256': sha(p)} for k, p in models.items()},
    'servers': {k: {'path': str(p), 'sha256': sha(p)} for k, p in servers.items()},
    'cases': [{'id': c['id'], 'payload_sha256': hashlib.sha256(json.dumps(c['payload'], sort_keys=True, ensure_ascii=False).encode()).hexdigest()} for c in cases],
    'manifest_sha256': initial,
    'source_sha256': sha(root / 'src/baxy_mind/llm.py'),
    'limits': {'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768, 'request_seconds': 40},
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

        def watch():
            while not stop.wait(.25):
                if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
                    violations.append('gpu_bound')
                if psutil.virtual_memory().available < 768 * 2**20:
                    violations.append('system_free_ram_bound')
                if violations:
                    client.close()
                    return

        guard = threading.Thread(target=watch, daemon=True)
        try:
            gpu.start()
            ram.start()
            guard.start()
            client.start_warmup()
            assert client.wait_warmup(90)
            assert gpu.telemetry_available and gpu.peak_mib is not None
            write(out / (key + '-command.json'), client._server_command())
            for case in cases:
                payload = copy.deepcopy(case['payload'])
                before = time.monotonic()
                client.begin_request(40)
                row = {'model': model_name, 'backend': backend, 'id': case['id']}
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
            resource = {'model': model_name, 'backend': backend, 'completed': completed, 'violations': violations, 'gpu_peak_mib': gpu.peak_mib, 'ram_peak_mib': ram.peak_mib, 'seconds': round(time.monotonic() - started, 3)}
            resources.append(resource)
            write(out / 'resources.json', resources)
            print(json.dumps(resource), flush=True)
        assert completed == 11 and not violations
assert sha(manifest) == initial
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
