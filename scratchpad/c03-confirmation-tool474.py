"""Measure whether stating the missing confirmation duty improves current source466."""
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
out = base / 'astra-confirmation-tool474'
private = local / 'C03-confirmation-tool474-private'
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
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=str(server), BAXY_MIND_NGL='99', BAXY_MIND_KV_CACHE_TYPE='q8_0')

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
initial = sha(manifest)
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Changed hypothesis after472/473 did not yield a usable instruction. Source466 unchanged, original confirmation instruction. Move unchanged situation from user text to native tool return for exact pendingAction.operation, retaining original user request/instructions. 438 showed this does not help completed memory results; do not repeat them. New population is prepared actions requiring decisions, not completed results, new input structured pendingAction. Six confirmation fixtures plus one unchanged memory control at officialQwen2507seed0/17. Each baseline first payload exactly equals468 before role transfer. Tool messages represent diagnostic supplied pending-operation outcomes; no callable tools are offered and no actual effect is run. Existing guards/retries retained; not model-only or product/UI/voice.',
    'criteria': 'Same465 rubric and all controls intact. Inspect actual template render, finish_reason, every first/final output. One protocol contrast only; if no useful improvement reject role transfer for this population too. No source or runtime promotion based on valid syntax.',
    'profile': {'temperature': .7, 'top_p': .8, 'top_k': 20, 'min_p': 0., 'presence_penalty': 0., 'repeat_penalty': 1., 'seeds': [0,17], 'max_tokens': 1024, 'enable_thinking': False, 'reasoning_budget_tokens': 0},
    'cases': [{'id': c['id'], 'request': c['request']} for c in cases],
    'model': str(model), 'model_sha256': sha(model), 'server': str(server), 'server_sha256': sha(server),
    'manifest_sha256': initial, 'source_sha256': sha(root / 'src/baxy_mind/llm.py'),
    'limits': {'composition_seconds': 55, 'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768}, 'private': str(private),
})
os.environ.update(BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private / 'compose-audit.jsonl'), BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')

prior_posts = [json.loads(line) for line in (local / 'C03-qwen-guarded468-private/posts.jsonl').open(encoding='utf-8-sig')]

class Measured(LlmRuntime):
    def _server_command(self):
        command = super()._server_command()
        command[command.index('--reasoning') + 1] = 'off'
        command[command.index('--reasoning-budget') + 1] = '0'
        return [*command, '--reasoning-format', 'deepseek', '--log-file', str(private / 'server.log')]

    def _post(self, payload, timeout=None, **kwargs):
        self.attempts += 1
        payload = copy.deepcopy(payload)
        payload.update(temperature=.7, top_p=.8, top_k=20, min_p=0., presence_penalty=0., repeat_penalty=1., seed=self.seed, max_tokens=1024, reasoning_budget_tokens=0)
        payload['chat_template_kwargs'] = {**payload.get('chat_template_kwargs', {}), 'enable_thinking': False}
        if self.attempts == 1:
            previous = next(r for r in prior_posts if r['id'] == self.case['id'] and r['seed'] == self.seed and r['variant'] == self.variant and r['attempt'] == 1)
            assert payload == previous['payload'], 'baseline payload changed before duty replacement'
        if self.variant == 'confirmation':
            body = payload['messages'][-1]['content']
            fact = next(line for line in body.splitlines() if line.startswith('situation: '))
            situation = json.loads(fact.removeprefix('situation: '))
            operation = situation['pendingAction']['operation']
            user = '\n'.join(line for line in body.splitlines() if line != fact)
            payload['messages'] = [*payload['messages'][:-1], {'role':'user','content':user},
                {'role':'assistant','content':None,'tool_calls':[{'id':'pending_operation','type':'function',
                    'function':{'name':operation,'arguments':'{}'}}]},
                {'role':'tool','tool_call_id':'pending_operation','name':operation,'content':fact}]
            if self.attempts == 1:
                template_request = urllib.request.Request(self._endpoint + '/apply-template',
                    data=json.dumps({'messages':payload['messages']}, ensure_ascii=False).encode(),
                    headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(template_request,timeout=10) as reply:
                    rendered = json.load(reply)
                append(private / 'template.jsonl', {'id':self.case['id'],'seed':self.seed,'rendered':rendered})
        remaining = min(55., timeout if timeout is not None else 55., self._remaining_request_timeout())
        request = urllib.request.Request(self._endpoint + '/v1/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=remaining) as reply:
            response = json.load(reply)
        append(private / 'posts.jsonl', {'id': self.case['id'], 'variant': self.variant, 'seed': self.seed, 'attempt': self.attempts, 'payload': payload, 'response': response})
        return response

client = Measured()
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
    write(out / 'command.json', client._server_command())
    pairs = [(c, 'baseline') for c in cases] + [(c, 'single-public-value') for c in cases if c['id'] == 'mixed-es']
    confirmations = json.loads((base / 'astra-memory-confirmation465/PREREG.json').read_text(encoding='utf-8-sig'))['cases']
    pairs += [(c, 'confirmation') for c in confirmations]
    pairs = [(c,v) for c,v in pairs if v == 'confirmation' or (c['id'] == 'actual437-t7' and v == 'baseline')]
    seeded_pairs = [(seed,c,v) for seed in [0,17] for c,v in pairs]
    for seed, case, variant in seeded_pairs:
        facts = copy.deepcopy(case['facts'])
        if variant == 'single-public-value':
            records = json.loads(facts['situation'])['observed']['records']
            values = [r['value'] for r in records if isinstance(r.get('value'), str) and r['value'] != '[REDACTED]' and 0 < len(r['value']) <= 256]
            assert len(values) == 1
            facts['requiredFacts'] = values
        client.case, client.variant, client.attempts, client.seed = case, variant, 0, seed
        before = time.monotonic()
        client.begin_request(55)
        row = {'id': case['id'], 'variant': variant, 'seed': seed}
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
    write(out / 'resources.json', {'completed': complete, 'violations': violations, 'gpu_peak_mib': gpu.peak_mib, 'ram_peak_mib': ram.peak_mib, 'seconds': round(time.monotonic() - started, 3), 'manifest_unchanged': sha(manifest) == initial})
assert complete and not violations and sha(manifest) == initial
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
