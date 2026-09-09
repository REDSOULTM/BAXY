"""Qualify Qwen3.5-9B with documented profile and current GDN backend on source466."""
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
out = base / 'astra-qwen9b-profile482'
private = local / 'C03-qwen9b-profile482-private'
out.mkdir(exist_ok=True)
assert not (out / "PREREG.json").exists()
private.mkdir(exist_ok=True)
assert not any(private.iterdir()), "Do not overwrite prior runtime evidence"
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
server = Path('D:/BAXYRuntime/assets/llama-b10865-cuda12.4/llama-server.exe')

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
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=str(server), BAXY_MIND_NGL='14', BAXY_MIND_KV_CACHE_TYPE='q8_0')

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
models = [('Qwen3.5-9B', Path('D:/BAXYRuntime/experiments/models/qwen35-9b-03b74727/Qwen3.5-9B-Q4_K_M.gguf'), '03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8')]
assert sha(server) == '16eac28198d6218a9892f08dac0f0c81612a72872b4dd9741c4c6c36f88c4fd7'
assert psutil.virtual_memory().available >= 4900 * 2**20, 'Wait for adequate memory; do not close user applications'
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
    'method': 'Qualify existing Qwen3.5-9B Q4_K_M on the current source466 confirmation contract with official nonthinking general-task profile and b10865 containing GDN28068 correction. Prior390/441 used old backend and fixed default/T0, on other responsibilities; their failures do not evaluate this profile or confirmation population. This is a candidate qualification, not causal attribution to one parameter or fair identical-config ranking. Native first messages exactly match468/481; only family-documented sampling changes (presence1.5). No472/474/476 instruction/role variants. NGL14/no-mmap/cache0 inherited measured390/441, context4096x3/KVq8/b2048/ub256 preserved. Six465 confirmations and two468 memory controls, seeds0/17, guarded source466 compositions. No UI/voice/fresh reserve/effects or registration changes.',
    'criteria': 'All six confirmations per seed must preserve pending action, target, supplied irreversible/privacy consequences with correct certainty, valid choices, language and natural brevity. Two memory controls must preserve value/subject/protection. Report every draft, finish reason, repair and resource. If it only exchanges omissions, no promotion or repeated seed/prompt sweep. 1024tokens and120s are diagnostic ceilings; length/timeouts are censored, not proof of inability. FreeRAM>=4900MiB before startup and768MiB throughout; GPU3800MiB guard.',
    'sources': ['https://huggingface.co/Qwen/Qwen3.5-9B', 'https://qwen.ai/blog?id=qwen3.5', 'https://github.com/ggml-org/llama.cpp/pull/28068', 'astra-qwen9b388/PREREG.json', 'astra-qwen9b-native390/RESULT.md', 'astra-memory-9b441/RESULT.md', 'astra-nightly-audit454/RESULT.md', 'astra-nightly-inference456/RESULT.md'],
    'profile': {'temperature': .7, 'top_p': .8, 'top_k': 20, 'min_p': 0., 'presence_penalty': 1.5, 'repeat_penalty': 1., 'seeds': [0,17], 'max_tokens': 1024, 'enable_thinking': False, 'reasoning_budget_tokens': 0},
    'cases': [{'id': c['id'], 'variant':v,'request': c['request']} for c,v in pairs],
    'models': [{'precision':tag,'path':str(path),'sha256':digest} for tag,path,digest in models], 'ngl':14, 'server': str(server), 'server_sha256': sha(server),
    'manifest_sha256': initial, 'source_sha256': source_sha,
    'limits': {'composition_seconds': 120, 'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768}, 'private': str(private),
})
os.environ.update(BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private / 'compose-audit.jsonl'), BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')

class Measured(LlmRuntime):
    def _server_command(self):
        command = super()._server_command()
        command[command.index('--reasoning') + 1] = 'off'
        command[command.index('--reasoning-budget') + 1] = '0'
        command[command.index('-ub') + 1] = '256'
        effective = [*command, '--reasoning-format', 'deepseek', '--verbosity','4','--log-file', str(private / f'server-{self.tag}.log')]
        write(out / f'command-{self.tag}.json', effective)
        return effective

    def _post(self, payload, timeout=None, **kwargs):
        self.attempts += 1
        payload = copy.deepcopy(payload)
        payload.update(temperature=.7, top_p=.8, top_k=20, min_p=0., presence_penalty=1.5, repeat_penalty=1., seed=self.seed, max_tokens=1024, reasoning_budget_tokens=0)
        payload['chat_template_kwargs'] = {**payload.get('chat_template_kwargs', {}), 'enable_thinking': False}
        if self.attempts == 1:
            reference = next(r for r in prior_posts if r['id'] == self.case['id'] and r['variant'] == self.variant and r['seed'] == self.seed and r['attempt'] == 1)
            expected = copy.deepcopy(reference['payload'])
            expected['presence_penalty'] = 1.5
            assert payload == expected, 'unexpected composition change beyond documented sampler'
        remaining = min(120., timeout if timeout is not None else 120., self._remaining_request_timeout())
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
            if client._endpoint and len(sampled_seeds) < 2:
                try:
                    with urllib.request.urlopen(client._endpoint+'/slots',timeout=.3) as reply: slots=json.load(reply)
                    for slot in slots:
                        seed=slot.get('params',{}).get('seed')
                        if slot.get('is_processing') and seed in {0,17} and seed not in sampled_seeds:
                            append(private/'effective-slots.jsonl',slot)
                            sampled_seeds.add(seed)
                except (OSError,ValueError): pass

    guard = threading.Thread(target=watch, daemon=True)
    complete = False
    try:
        gpu.start(); ram.start(); guard.start()
        client.start_warmup()
        assert client.wait_warmup(90) and gpu.telemetry_available
        write(out / f'command-{tag}.json', client._server_command())
        for route,body in [('/props',None),('/apply-template',prior_posts[0]['payload'])]:
            req = urllib.request.Request(client._endpoint+route, data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as response: write(private / (tag+route.replace('/','-')+'.json'),json.load(response))
        seeded_pairs = [(seed,c,v) for seed in [0,17] for c,v in pairs]
        for seed, case, variant in seeded_pairs:
            facts = copy.deepcopy(case['facts'])
            client.case, client.variant, client.attempts, client.seed = case, variant, 0, seed
            before = time.monotonic()
            client.begin_request(120)
            row = {'precision':tag,'id': case['id'], 'variant': variant, 'seed': seed}
            try:
                row['answer'] = client.compose_user_message(case['request'], 'confirmation' if variant == 'confirmation' else 'status', facts, timeout=120)
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
write(out / 'RESULT.json', {'completed':True,'compositions':16,'resources':all_resources,'source_unchanged':sha(root / 'src/baxy_mind/llm.py')==source_sha,'manifest_unchanged':sha(manifest)==initial,'needs_semantic_adjudication':True})
write(out / 'PINS.json', {p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
