"""Pinned9B partial offload on four frozen native controls, with owned resource stop."""
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

out = root / 'artifacts/comprobaciones/C03/astra-qwen9b-native389'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-qwen9b-native389-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
prior = json.loads((root / 'artifacts/comprobaciones/C03/astra-identity-scope387/PREREG.json').read_text(encoding='utf-8'))
download = json.loads((root / 'artifacts/comprobaciones/C03/astra-qwen9b388/DOWNLOAD.json').read_text(encoding='utf-8'))
model = Path(download['path'])
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
assert sha(model) == download['sha256'] == '03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8'
assert sha(manifest) == prior['manifest_sha256']
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': prior['cases'],
    'reference': prior['reference'], 'model': str(model), 'model_sha256': sha(model),
    'backend_sha256': sha(config['llama_server']), 'manifest_sha256': sha(manifest),
    'ngl': 14, 'method': 'Four identical original-description native controls387. Only GGUF4B→9B and mandatory partial offload99→14 change. Same captured BAXY native prompt, tools, history, sampler, token allowance and transport/template handling. No account-scope description variant, App, guarded mind, operations, UI, voice or fresh-human acceptance. This is a capability/resource diagnostic, not model-alone or latency acceptance.',
    'resource_limits': {'gpu_stop_mib': 3800, 'hard_product_ceiling_mib': 4096, 'minimum_free_ram_mib': 768},
    'budget': '120s per native request to distinguish capability from CPU offload latency; report durations, never imply this fits current product turn budgets. Owned process-tree GPU/RAM sampled every250ms, independent watchdog closes the runtime at the conservative bound. Telemetry absence blocks case execution.',
    'research': '388 pins source/quantization/license/official non-thinking settings. This first comparison deliberately retains387 sampler rather than changing model and sampling together. Start log records actual GGUF architecture and tensor placement; command includes only diagnostic log-file addition.',
    'private': str(private)}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL='14')
class LoggedRuntime(LlmRuntime):
    def _server_command(self):
        return [*super()._server_command(), '--log-file', str(private / 'server.log')]
client = LoggedRuntime()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
stop = threading.Event()
violation = []
def guard():
    while not stop.wait(0.25):
        if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
            violation.append('owned_gpu_conservative_bound')
        if psutil.virtual_memory().available < 768 * 2**20:
            violation.append('system_free_ram_bound')
        if violation:
            client.close()
            return
watch = threading.Thread(target=guard, daemon=True)
started = time.monotonic()
complete = False
try:
    gpu.start()
    ram.start()
    watch.start()
    client.start_warmup()
    assert client.wait_warmup(120), 'model did not become ready'
    assert not violation, violation
    assert gpu.telemetry_available and gpu.peak_mib is not None, 'owned GPU telemetry unavailable'
    (out / 'command.json').write_text(json.dumps(client._server_command(), indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'ready_seconds': round(time.monotonic()-started, 3), 'gpu_peak_mib': gpu.peak_mib, 'ram_peak_mib': ram.peak_mib}), flush=True)
    for case in prior['cases']:
        payload = copy.deepcopy(prior['reference'])
        payload['messages'][-1]['content'] = case['text']
        if case['id'] == 'actual-human-es':
            assert payload == prior['reference']
        assert not violation, violation
        before = time.monotonic()
        client.begin_request(120)
        try:
            response = client._post(payload)
        finally:
            client.end_request()
        row = {'id': case['id'], 'seconds': round(time.monotonic()-before, 3), 'choice': response['choices'][0]}
        with (private / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'id': case['id'], 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
        with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(json.dumps(row, ensure_ascii=True), flush=True)
    complete = True
finally:
    stop.set()
    client.close()
    watch.join(timeout=5)
    gpu.stop()
    ram.stop()
    (out / 'RESOURCES.json').write_text(json.dumps({'completed': complete, 'violations': violation,
        'gpu_peak_mib': gpu.peak_mib, 'gpu_telemetry_available': gpu.telemetry_available,
        'ram_peak_mib': ram.peak_mib, 'seconds': round(time.monotonic()-started, 3),
        'manifest_unchanged': sha(manifest) == prereg['manifest_sha256']}, indent=2) + '\n', encoding='utf-8')
