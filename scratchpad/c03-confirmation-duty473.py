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
out = base / 'astra-confirmation-duty473'
private = local / 'C03-confirmation-duty473-private'
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
model = Path('D:/BAXYRuntime/experiments/models/baxy-gemma4-e2b-published-f9b84ecd/gemma-4-E2B-it-Q4_K_M.gguf')
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
    'method': 'Same task-duty replacement472 applied to publishedGemmaE2B actual guarded composer/source466. No new wording variant. Exact baseline first payload compared to465 (467 for export) before replacement; two documented thinking seeds0/17,6confirmation cases each. Sources/method model-specific in465/470, lazy462 and explicit globalbudget-1 inherited correctly. No effects/voice/UI/fresh credit.',
    'criteria': 'Same465 decision facts and naturalness; compare to465/467 by seed, preserve failures. No source/runtime promotion by partial coverage. Baseline transport must match exactly.',
    'profile': {'temperature':1.,'top_p':.95,'top_k':64,'min_p':0.,'presence_penalty':0.,'repeat_penalty':1.,'seeds':[0,17],'max_tokens':3072,'thinking':True},
    'model': str(model), 'model_sha256': sha(model), 'server': str(server), 'server_sha256': sha(server),
    'manifest_sha256': initial, 'source_sha256': sha(root / 'src/baxy_mind/llm.py'),
    'limits': {'composition_seconds': 55, 'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768}, 'private': str(private),
})
os.environ.update(BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private / 'compose-audit.jsonl'), BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')

prior_posts = [json.loads(line) for name in ['C03-memory-confirmation465-private','C03-export-confirmation467-private'] for line in (local / name / 'posts.jsonl').open(encoding='utf-8-sig') if (name.endswith('467-private') or json.loads(line)['id'] != 'export-es')]

class Measured(LlmRuntime):
    def _server_command(self):
        command = super()._server_command()
        command[command.index('--reasoning') + 1] = 'on'
        command[command.index('--reasoning-budget') + 1] = '-1'
        return [*command, '--reasoning-format', 'deepseek', '--lazy-mode', 'on', '--log-file', str(private / 'server.log')]

    def _post(self, payload, timeout=None, **kwargs):
        self.attempts += 1
        payload = copy.deepcopy(payload)
        payload.update(temperature=1., top_p=.95, top_k=64, min_p=0., presence_penalty=0., repeat_penalty=1., seed=self.seed, max_tokens=3072, reasoning_budget_tokens=-1)
        payload['chat_template_kwargs'] = {**payload.get('chat_template_kwargs', {}), 'enable_thinking': True}
        if self.attempts == 1:
            previous = next(r for r in prior_posts if r['id'] == self.case['id'] and r['profile'] == f'documented-thinking-True-seed-{self.seed}' and r['attempt'] == 1)
            assert payload == previous['payload'], 'baseline payload changed before duty replacement'
        if self.variant == 'confirmation':
            old = ('Request a decision about the pending action and its target '
                   'in everyday language, so the person knows what they authorize. ')
            replacement = ('Explain the pending action and its target, the supplied reason for confirmation, '
                           'and all the supplied consequences relevant to this decision. '
                           'Preserve their certainty: a possible consequence is not an observed event. ')
            replaced = 0
            for message in payload['messages']:
                replaced += message['content'].count(old)
                message['content'] = message['content'].replace(old, replacement)
            assert replaced == 1
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
    pairs = [(c,v) for c,v in pairs if v == 'confirmation']
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
