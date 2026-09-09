"""Compare documented Gemma profiles for existing memory confirmations."""
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
out = base / 'astra-export-confirmation467'
private = local / 'C03-export-confirmation467-private'
out.mkdir(exist_ok=True)
private.mkdir(exist_ok=True)
assert not (out / 'PREREG.json').exists()
assert not (private / 'posts.jsonl').exists()
prior = local / 'C03-private-product464-private'
prereg = json.loads((base / 'astra-private-product464/PREREG.json').read_text(encoding='utf-8-sig'))
model = prereg['diagnostic_model_override']['path']
server = prereg['diagnostic_backend_override']['path']
audit = [json.loads(x) for x in (prior / 'compose-audit.jsonl').read_text(encoding='utf-8-sig').splitlines()]
actual = next(r for r in audit if r.get('trace') == 't1' and r.get('intent') == 'confirmation' and r.get('stage') == 'first')
posts = [json.loads(x) for x in (prior / 'http-posts.jsonl').read_text(encoding='utf-8-sig').splitlines()]
reference = next(r['payload'] for r in posts if r.get('id') == 2 and r['stage'] == 'request')
reference.pop('reasoning_budget_tokens')
original = json.loads(actual['situation'])
cases = []
for key, request, operation, cause in [
    ('actual-enable-en', 'My name is Jordan. Remember my name.', 'memory.enable', 'memory_enable'),
    ('enable-es', 'Me llamo Marta. Recuerda mi nombre.', 'memory.enable', 'memory_enable'),
    ('forget-es', 'Olvida mi color favorito.', 'memory.forget', 'memory_forget_irreversible'),
    ('forget-en', 'Forget my favorite color.', 'memory.forget', 'memory_forget_irreversible'),
    ('sensitive-en', 'Save my secret in your memory.', 'memory.sensitive.save', 'memory_sensitive_save'),
    ('export-es', 'Exporta mis recuerdos guardados.', 'memory.export', 'memory_export_privacy'),
]:
    situation = copy.deepcopy(original)
    situation['pendingAction']['operation'] = operation
    situation['cause'] = cause
    if operation == 'memory.export':
        situation.update(destination='Documents/BAXY', mayRedirectOrSync=True)
    facts = {'situation': json.dumps(situation, ensure_ascii=False), 'requiredResponseWords': original['choices']}
    cases.append({'id': key, 'request': request, 'facts': facts})


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def append(path, value):
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False) + '\n')


for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=model, BAXY_MIND_LLAMA_SERVER=server, BAXY_MIND_NGL='99', BAXY_MIND_KV_CACHE_TYPE='q8_0')


class Captured(Exception):
    pass


class Offline(LlmRuntime):
    def _post(self, payload, *args, **kwargs):
        write(private / 'offline-first.json', {'expected': reference, 'actual': payload})
        assert payload == reference, 'First payload differs from actual464; stop before model evaluation'
        raise Captured()


offline = Offline()
try:
    try:
        offline.compose_user_message(cases[0]['request'], 'confirmation', cases[0]['facts'])
    except Captured:
        pass
finally:
    offline.close()

profiles = [{'id': 'current-greedy', 'sampling': {'temperature': 0.0}, 'thinking': False, 'max_tokens': 256}]
for thinking in [False, True]:
    for seed in [0, 17]:
        profiles.append({'id': f'documented-thinking-{thinking}-seed-{seed}', 'sampling': {'temperature': 1.0, 'top_p': .95, 'top_k': 64, 'min_p': 0., 'presence_penalty': 0., 'repeat_penalty': 1., 'seed': seed}, 'thinking': thinking, 'max_tokens': 3072 if thinking else 1024})
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
initial = sha(manifest)
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Source466 vs465: only projection preserves existing destination and mayRedirectOrSync for confirmation. Same documented Gemma profiles, original six prepared fixtures; execute only export at all5profiles and actual enableT0 as unchanged control (6compositions total). Existing first-enable offline equality464 still passes. No repeated other four cases because their payload fields are unchanged and owner tests cover projection. Full composer/guards, no prompt edits. Expect model can now name observed export destination and sync risk; result may still fail semantically, report individually. Source466 owner1404pass/0skips and Fast3.66s already passed.',
    'criteria': 'Export must explain pending export to Documents/BAXY and possible redirection/sync, both choices and no success claim; control identical. Count all fixed profiles/seeds, not best-of. No global candidate promotion or fresh acceptance.',
    'profiles': profiles, 'cases': cases,
    'model': model, 'model_sha256': sha(model), 'server': server, 'server_sha256': sha(server),
    'source_sha256': sha(root / 'src/baxy_mind/llm.py'), 'manifest_sha256': initial,
    'limits': {'composition_seconds': 55, 'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768},
})
os.environ.update(BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private / 'compose-audit.jsonl'), BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')


class Measured(LlmRuntime):
    def _server_command(self):
        command = super()._server_command()
        command[command.index('--reasoning') + 1] = 'on'
        command[command.index('--reasoning-budget') + 1] = '-1'
        return [*command, '--reasoning-format', 'deepseek', '--lazy-mode', 'on', '--log-file', str(private / 'server.log')]

    def _post(self, payload, timeout=None, **kwargs):
        self.attempts += 1
        payload = copy.deepcopy(payload)
        payload.update(**self.profile['sampling'], max_tokens=self.profile['max_tokens'], reasoning_budget_tokens=-1 if self.profile['thinking'] else 0)
        payload['chat_template_kwargs'] = {**payload.get('chat_template_kwargs', {}), 'enable_thinking': self.profile['thinking']}
        remaining = min(55., timeout if timeout is not None else 55., self._remaining_request_timeout())
        request = urllib.request.Request(self._endpoint + '/v1/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=remaining) as reply:
            response = json.load(reply)
        append(private / 'posts.jsonl', {'id': self.case['id'], 'profile': self.profile['id'], 'attempt': self.attempts, 'payload': payload, 'response': response})
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
    gpu.start()
    ram.start()
    guard.start()
    client.start_warmup()
    assert client.wait_warmup(90) and gpu.telemetry_available
    write(out / 'command.json', client._server_command())
    for profile in profiles:
        for case in cases:
            if case['id'] != 'export-es' and not (profile['id'] == 'current-greedy' and case['id'] == 'actual-enable-en'):
                continue
            client.profile, client.case, client.attempts = profile, case, 0
            before = time.monotonic()
            client.begin_request(55)
            row = {'id': case['id'], 'profile': profile['id']}
            try:
                row['answer'] = client.compose_user_message(case['request'], 'confirmation', case['facts'], timeout=55)
            except (RuntimeError, TimeoutError) as error:
                row['error'] = type(error).__name__ + ': ' + str(error)
            finally:
                client.end_request()
            row.update(attempts=client.attempts, seconds=round(time.monotonic() - before, 3))
            append(out / 'replies.jsonl', row)
            print(json.dumps(row, ensure_ascii=True), flush=True)
    complete = True
finally:
    stop.set()
    client.close()
    guard.join(timeout=5)
    gpu.stop()
    ram.stop()
    write(out / 'resources.json', {'completed': complete, 'violations': violations, 'gpu_peak_mib': gpu.peak_mib, 'ram_peak_mib': ram.peak_mib, 'seconds': round(time.monotonic() - started, 3), 'manifest_unchanged': sha(manifest) == initial})
assert complete and not violations and sha(manifest) == initial
