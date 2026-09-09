"""Isolate native grammar with the exact captured prompt tokens and sampler."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import threading
import time
import urllib.request
import re

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'src')]
import psutil
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = base / 'astra-gemma-grammar496'
private = local / 'C03-gemma-grammar496-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def append(path, value):
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')

source = base / 'astra-gemma-parse494/replies.jsonl'
references = [json.loads(line) for line in source.open(encoding='utf-8-sig')]
assert len(references) == 3
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
manifest_sha = sha(manifest)
model = Path('D:/BAXYRuntime/experiments/models/baxy-gemma4-e2b-published-f9b84ecd/gemma-4-E2B-it-Q4_K_M.gguf')
server = Path('D:/BAXYRuntime/assets/llama-v0.4.0-b10809-cuda12.4/llama-server.exe')
write(out / 'PREREG.json', {
    'method': '495 stopped before any generation with HTTP400: serialized output settings differ from input types (pinned server-schema.cpp291/337:chat_format numeric input,string output;preserved_tokens strings input,IDs output).496 converts preserved IDs to exact token pieces and verifies round-trip; omits output-only parser name for both raw branches. Exact three494 captured native prompts and generation settings, replayed as token arrays through local /completion. Both branches use the same raw endpoint. Tokenize with add_special:false/parse_special:true; assert prompt token count equals captured494. Compare original native lazy grammar against empty grammar/no triggers. Preserve stopping, samplers, context, prompt, preserved tokens and thinking input. Seeds0 for all three and17 for owner51; eight calls total. No parser output manipulation, forced tool list, clipping, examples, source changes or effects.',
    'hypothesis': '494 raw text itself contains every extra parsed call, so output parsing did not insert them. However native generation is grammar-constrained; a repeated tool-call root may alter termination. Separate constraint effects from weights before attributing the loop to Gemma.',
    'reference_sha256': sha(source), 'model_sha256': sha(model), 'server_sha256': sha(server),
    'manifest_sha256': manifest_sha, 'private': str(private),
    'criteria': 'Compare full raw sequences and stop causes; every extra action or missing effect fails. Verify effective sampler/grammar and prompt counts. No fresh acceptance, whole-product credit or automatic promotion.',
    'sources': ['https://github.com/ggml-org/llama.cpp/blob/5266f24da/tools/server/server-task.cpp#L339',
                'https://github.com/ggml-org/llama.cpp/blob/5266f24da/common/chat.cpp#L3697',
                'https://arxiv.org/abs/2408.02442', 'https://blog.dottxt.ai/say-what-you-mean.html'],
    'limits': {'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768, 'request_seconds': 90},
})
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=str(server),
                  BAXY_MIND_NGL='99', BAXY_MIND_KV_CACHE_TYPE='q8_0')

class Measured(LlmRuntime):
    def _server_command(self):
        command = super()._server_command()
        command[command.index('--reasoning') + 1] = 'on'
        command[command.index('--reasoning-budget') + 1] = '-1'
        command += ['--reasoning-format', 'deepseek', '--lazy-mode', 'on',
                    '--log-file', str(private / 'server.log')]
        write(private / 'effective-server-command.json', command)
        return command

client = Measured()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
stop = threading.Event()
violations = []

def watch():
    while not stop.wait(.25):
        if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
            violations.append('gpu_bound')
        if psutil.virtual_memory().available < 768 * 2**20:
            violations.append('free_ram_bound')
        if violations:
            client.close()
            return

def post(endpoint, payload):
    request = urllib.request.Request('http://127.0.0.1:' + str(client._port) + endpoint,
                                     data=json.dumps(payload).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        write(private/'http-error.json',{'status':error.code,'body':error.read().decode('utf-8','replace')})
        raise

guard = threading.Thread(target=watch, daemon=True)
started = time.monotonic()
complete = False
try:
    gpu.start(); ram.start(); guard.start()
    client.start_warmup(); assert client.wait_warmup(90)
    for reference in references:
        captured = reference['response']['__verbose']
        tokens = post('/tokenize', {'content': captured['prompt'],
                                    'add_special': False, 'parse_special': True})['tokens']
        assert len(tokens) == captured['tokens_evaluated'], 'Prompt mismatch; do not infer grammar effect'
        for seed in ([0, 17] if reference['id'] == 'owner51-seed0' else [0]):
            for variant in ['native_grammar', 'no_grammar']:
                payload = copy.deepcopy(captured['generation_settings'])
                payload.pop('chat_format',None)  # Output name differs from input numeric enum; no parser used here.
                preserved=[]
                for token in payload['preserved_tokens']:
                    piece=post('/detokenize',{'tokens':[token]})['content']
                    assert post('/tokenize',{'content':piece,'add_special':False,'parse_special':True})['tokens']==[token]
                    preserved.append(piece)
                payload['preserved_tokens']=preserved
                payload.update(prompt=tokens, seed=seed, stream=False, cache_prompt=False, return_tokens=True)
                if variant == 'no_grammar':
                    payload.update(grammar='', grammar_lazy=False, grammar_triggers=[])
                append(private / 'requests.jsonl', {'id': reference['id'], 'seed': seed,
                                                   'variant': variant, 'payload': payload})
                before = time.monotonic()
                response = post('/completion', payload)
                row = {'id': reference['id'], 'seed': seed, 'variant': variant,
                       'seconds': round(time.monotonic() - before, 3), 'response': response}
                append(private / 'posts.jsonl', row)
                append(out / 'replies.jsonl', row)
                generated = response.get('content', '').split('<channel|>')[-1]
                print(json.dumps({'id': reference['id'], 'seed': seed, 'variant': variant,
                                  'stop_type': response.get('stop_type'),
                                  'tools': re.findall(r'<\|tool_call>call:([\w_\.]+)', generated),
                                  'tokens': response.get('tokens_predicted')}, ensure_ascii=True), flush=True)
                assert response['generation_settings']['grammar'] == payload['grammar']
                assert response['tokens_evaluated'] == len(tokens)
                effective=response['generation_settings']
                for key in ['temperature','top_p','top_k','min_p','repeat_penalty','presence_penalty','seed','ignore_eos','samplers','stop']:
                    assert effective[key]==payload[key], (key,effective[key],payload[key])
                assert sorted(effective['preserved_tokens'])==sorted(captured['generation_settings']['preserved_tokens'])
                if violations:
                    raise RuntimeError('Resource guard stopped the diagnostic')
    complete = True
finally:
    stop.set(); client.close(); guard.join(timeout=5); gpu.stop(); ram.stop()
    write(out / 'RESOURCES.json', {'completed': complete, 'violations': violations,
                                  'gpu_peak_mib': gpu.peak_mib, 'ram_peak_mib': ram.peak_mib,
                                  'seconds': round(time.monotonic() - started, 3),
                                  'manifest_unchanged': sha(manifest) == manifest_sha})
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
