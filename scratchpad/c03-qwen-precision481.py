"""Matched registered-checkpoint Q4 vs Q8, preserving source466 and documented settings."""
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
out = base / 'astra-qwen-precision481'
private = local / 'C03-qwen-precision481-private'
out.mkdir(exist_ok=True)
assert not (out / "PREREG.json").exists()
private.mkdir(exist_ok=False)
original = {}
for line in (local / 'C03-private-product437-private/compose-audit.jsonl').open(encoding='utf-8-sig'):
    row = json.loads(line)
    if row.get('stage') == 'first' and row.get('situation'):
        situation = json.loads(row['situation'])
        if situation.get('operation', '').startswith('memory.') and situation.get('succeeded'):
            original.setdefault(situation['operation'], situation)
cases = []
for line in (local / 'C03-memory-gemma444-private/posts.jsonl').open(encoding='utf-8-sig'):
    row = json.loads(line)
    payload = row['payload']
    body = payload['messages'][-1]['content']
    view = json.loads(next(x.removeprefix('situation: ') for x in body.splitlines() if x.startswith('situation: ')))
    situation = copy.deepcopy(original[view['operation']])
    situation['observed'] = view['seen']
    facts = {'situation': json.dumps(situation, ensure_ascii=False)}
    literals = next((x.removeprefix('Hechos: ') for x in body.splitlines() if x.startswith('Hechos: ')), None)
    if literals:
        values = [r['value'] for r in view['seen'].get('records', []) if isinstance(r.get('value'), str) and r['value'] != '[REDACTED]' and r['value'] in literals]
        if len(values) == 1:
            facts['requiredFacts'] = values
    if row['id'] == 'two-records':
        payload = copy.deepcopy(payload)
        payload['messages'][-1]['content'] = '\n'.join(line for line in body.splitlines() if not line.startswith(('Contrato literal de salida:', 'Acciones:', 'Palabras:', 'Hechos:')))
    cases.append({'id': row['id'], 'request': body.splitlines()[0], 'facts': facts, 'reference': payload})
assert len(cases) == 11
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
model = Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf')
server = Path('D:/BAXYRuntime/assets/llama-v0.4.0-b10809-cuda12.4/llama-server.exe')

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

def append(path, value):
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False) + '\n')

for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=str(server), BAXY_MIND_NGL='24', BAXY_MIND_KV_CACHE_TYPE='q8_0')

class Captured(Exception):
    pass

class Offline(LlmRuntime):
    def _post(self, payload, *args, **kwargs):
        if payload != self.reference:
            write(private / 'offline-mismatch.json', {'expected': self.reference, 'actual': payload})
            raise AssertionError('reconstructed first composition differs; do not infer')
        raise Captured()

offline = Offline()
try:
    for case in cases:
        offline.reference = case['reference']
        try:
            offline.compose_user_message(case['request'], 'status', case['facts'])
        except Captured:
            pass
        else:
            raise AssertionError('no first payload captured')
finally:
    offline.close()
models = [
    ('Q4_K_M', model, '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'),
    ('Q8_0', Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-q8-a06e946b/Qwen3-4B-Instruct-2507-Q8_0.gguf'), '391c1e410fd9f4cf2de2b510273b56a84c19ce18f4fa3bfb3774031dac4ef068'),
]
models.reverse()  # Resource-qualify Q8 before paying another matched Q4 baseline.
for tag,path,digest in models:
    assert sha(path) == digest
confirmations = json.loads((base / 'astra-memory-confirmation465/PREREG.json').read_text(encoding='utf-8-sig'))['cases']
pairs = [(c,'baseline') for c in cases if c['id'] in {'actual437-t7','redacted-en'}]
pairs += [(c,'confirmation') for c in confirmations]
assert len(pairs) == 8
prior_posts = [json.loads(line) for line in (local / 'C03-qwen-guarded468-private/posts.jsonl').open(encoding='utf-8-sig')]
source_sha = sha(root / 'src/baxy_mind/llm.py')
initial = sha(manifest)
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'After479/480Q8 reachedGPUguard withNGL26 and microbatch change insufficient, reduceNGL26to24 for BOTH precisions, keepub128/restsame. Q8 is qualified first to avoid repeatingQ4 if it still does not fit. Matched weight precision qualification/comparison, not another task instruction. Q4_K_M andQ8_0 exact same Unsloth checkpoint/revisiona06e946b; b10809/NGL24 for BOTH, preserving4096x3/KVq8/b2048/ub128/no-mmap/cache0 and documented sampler/seeds0,17. Resource gate first for each. Each first payload exactly equals468 before inference; no472/474/476 task/protocol modifications. Eight development cases (6confirmations and2memory controls) per seed per precision=32guarded compositions. Offloading-policy contrast to468 allGPU is a separate confound explicitly controlled by matchedNGL24 baseline here. No physical effect, callable tool, UI/voice/reserve or source/runtime edits.',
    'criteria': 'Same465/468 factual/natural criteria. Judge all32 finals and inspect first drafts/finish_reason/retries. No entire model-family conclusion from a quant. If precision changes only failure variants, do not adopt or launch other intermediate quantizations without a new reason. Do not infer full-product resources from this composer. GPU3800MiB/freeRAM768MiB guards retained; no other processes closed or silent context reduction.',
    'profile': {'temperature': .7, 'top_p': .8, 'top_k': 20, 'min_p': 0., 'presence_penalty': 0., 'repeat_penalty': 1., 'seeds': [0,17], 'max_tokens': 1024, 'enable_thinking': False, 'reasoning_budget_tokens': 0},
    'cases': [{'id': c['id'], 'variant':v,'request': c['request']} for c,v in pairs],
    'models': [{'precision':tag,'path':str(path),'sha256':digest} for tag,path,digest in models], 'ngl':24, 'server': str(server), 'server_sha256': sha(server),
    'manifest_sha256': initial, 'source_sha256': source_sha,
    'limits': {'composition_seconds': 55, 'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768}, 'private': str(private),
})
os.environ.update(BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private / 'compose-audit.jsonl'), BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')

class Measured(LlmRuntime):
    def _server_command(self):
        command = super()._server_command()
        command[command.index('--reasoning') + 1] = 'off'
        command[command.index('--reasoning-budget') + 1] = '0'
        command[command.index('-ub') + 1] = '128'
        effective = [*command, '--reasoning-format', 'deepseek', '--verbosity','4','--log-file', str(private / f'server-{self.tag}.log')]
        write(out / f'command-{self.tag}.json', effective)
        return effective

    def _post(self, payload, timeout=None, **kwargs):
        self.attempts += 1
        payload = copy.deepcopy(payload)
        payload.update(temperature=.7, top_p=.8, top_k=20, min_p=0., presence_penalty=0., repeat_penalty=1., seed=self.seed, max_tokens=1024, reasoning_budget_tokens=0)
        payload['chat_template_kwargs'] = {**payload.get('chat_template_kwargs', {}), 'enable_thinking': False}
        if self.attempts == 1:
            reference = next(r for r in prior_posts if r['id'] == self.case['id'] and r['variant'] == self.variant and r['seed'] == self.seed and r['attempt'] == 1)
            assert payload == reference['payload'], 'unexpected composition change before precision test'
        remaining = min(55., timeout if timeout is not None else 55., self._remaining_request_timeout())
        request = urllib.request.Request(self._endpoint + '/v1/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=remaining) as reply:
            response = json.load(reply)
        append(private / 'posts.jsonl', {'precision':self.tag,'id': self.case['id'], 'variant': self.variant, 'seed': self.seed, 'attempt': self.attempts, 'payload': payload, 'response': response})
        return response

all_resources = []
for tag, model_path, model_digest in models:
    os.environ['BAXY_MIND_LLM_GGUF'] = str(model_path)
    client = Measured()
    client.tag = tag
    gpu, ram = ProcessTreeGpuSampler(os.getpid()), RamSampler(os.getpid())
    stop = threading.Event()
    violations = []
    started = time.monotonic()

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
    complete = False
    try:
        gpu.start(); ram.start(); guard.start()
        client.start_warmup()
        assert client.wait_warmup(90) and gpu.telemetry_available
        write(out / f'command-{tag}.json', client._server_command())
        seeded_pairs = [(seed,c,v) for seed in [0,17] for c,v in pairs]
        for seed, case, variant in seeded_pairs:
            facts = copy.deepcopy(case['facts'])
            client.case, client.variant, client.attempts, client.seed = case, variant, 0, seed
            before = time.monotonic()
            client.begin_request(55)
            row = {'precision':tag,'id': case['id'], 'variant': variant, 'seed': seed}
            try:
                row['answer'] = client.compose_user_message(case['request'], 'confirmation' if variant == 'confirmation' else 'status', facts, timeout=55)
            except (RuntimeError, TimeoutError) as error:
                row['error'] = type(error).__name__ + ': ' + str(error)
            finally:
                client.end_request()
            row.update(attempts=client.attempts, seconds=round(time.monotonic() - before, 3))
            append(out / 'replies.jsonl', row)
            print(json.dumps(row, ensure_ascii=True), flush=True)
        complete = True
    finally:
        stop.set(); client.close(); guard.join(timeout=5); gpu.stop(); ram.stop()
        write(out / f'resources-{tag}.json', {'completed': complete, 'violations': violations, 'gpu_peak_mib': gpu.peak_mib, 'ram_peak_mib': ram.peak_mib, 'seconds': round(time.monotonic() - started, 3), 'manifest_unchanged': sha(manifest) == initial})
    assert complete and not violations and sha(manifest) == initial
    assert sha(root / 'src/baxy_mind/llm.py') == source_sha
    all_resources.append(json.loads((out / f'resources-{tag}.json').read_text(encoding='utf-8-sig')))
write(out / 'RESULT.json', {'completed':True,'compositions':32,'resources':all_resources,'source_unchanged':sha(root / 'src/baxy_mind/llm.py')==source_sha,'manifest_unchanged':sha(manifest)==initial,'needs_semantic_adjudication':True})
write(out / 'PINS.json', {p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
