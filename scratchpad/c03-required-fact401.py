"""Measure existing literal-fact transport on private read results, no source edit."""
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'src')]
import psutil
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

out = root / 'artifacts/comprobaciones/C03/astra-required-fact401'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-required-fact401-private'
source = private.parent / 'C03-stored-product393b-private'
audit = [json.loads(line) for line in (source / 'compose-audit.jsonl').open(encoding='utf-8-sig')]
wire = [json.loads(line) for line in (source / 'http-posts.jsonl').open(encoding='utf-8-sig')]
cases = []
for identifier, trace, post in [('stored-en', 't3', 5), ('stored-es', 't5', 10)]:
    row = next(r for r in audit if r['trace'] == trace and r['stage'] == 'first')
    payload = next(r['payload'] for r in wire if r.get('stage') == 'request' and r['id'] == post)
    cases.append({'id': identifier, 'request': payload['messages'][-1]['content'].split('\nsituation:')[0],
                  'situation': json.loads(row['situation']), 'reference': payload,
                  'origin': f'actual393b/{trace}/post{post}',
                  'expected': 'Report the stored name Jordan; neither empty memory nor BAXY calling itself Jordan.'})
for identifier, original, request, label, value in [
    ('new-name-en', 0, 'What name have you saved in private memory?', 'name', 'Priya'),
    ('new-name-es', 1, '¿Qué nombre tienes guardado en tu memoria privada?', 'name', 'Renata'),
    ('preference-en', 0, 'What is my saved favorite color?', 'favorite color', 'indigo'),
    ('preference-es', 1, '¿Qué color favorito tengo guardado?', 'color favorito', 'turquesa'),
    ('empty-en', 0, 'What name have you saved in private memory?', None, None),
    ('redacted-es', 1, '¿Qué tienes guardado en la memoria privada?', 'secret', '[REDACTED]'),
]:
    case = copy.deepcopy(cases[original])
    case.update(id=identifier, request=request, origin='synthetic projected-record control')
    case.pop('reference')
    case['situation']['observed'] = {'shown': int(value is not None), 'total': int(value is not None),
                                     'records': [] if value is None else [{'label': label, 'value': value}], 'replayed': False}
    case['expected'] = ('Report absence without inventing a value.' if value is None else
                        'Explain that the stored value is protected, without disclosing or fabricating it.' if value == '[REDACTED]' else
                        f'Report the stored {label}: {value}; do not transfer its subject to BAXY or claim a new save.')
    cases.append(case)

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def facts(case, variant):
    result = {'situation': json.dumps(case['situation'], ensure_ascii=False)}
    records = case['situation']['observed']['records']
    if variant == 'retain-value' and len(records) == 1:
        value = records[0].get('value')
        if isinstance(value, str) and value != '[REDACTED]' and 0 < len(value) <= 256:
            result['requiredFacts'] = [value]
    return result

for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'],
                  BAXY_MIND_NGL=str(config['ngl']))

class Captured(Exception):
    pass

class Offline(LlmRuntime):
    def _post(self, payload, *args, **kwargs):
        assert payload == self.reference, 'reconstructed baseline differs from captured393b'
        raise Captured()

offline = Offline()
try:
    for case in cases[:2]:
        offline.reference = case['reference']
        try:
            offline.compose_user_message(case['request'], 'status', facts(case, 'baseline'))
        except Captured:
            pass
        else:
            raise AssertionError('no captured baseline')
finally:
    offline.close()

out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
    'method': 'Actual guarded LlmRuntime.compose_user_message; eight fixed read-result cases, baseline and retain-value. Only facts.requiredFacts carries the single projected safe value; existing compositor prompt and validation unchanged. Offline baseline payload equality393b already passed for both actual cases; assert it again live. No sidecar/App/effects, tool roles, answer injection, source edits, sampler or model change. Empty and redacted controls retain identical facts in both arms.',
    'inheritance': 'UserMessagePolicy.RequiredStructuredLiterals preserves reason/title, omits projected records. ModelMessageComposer already transports requiredFacts; llm renders and validates the existing literal contract.378b established exact reconstruction of real compose payload.347 tool-result-role and392 contextual-resolver failures excluded. Historical2_memoria.md:115-159 requires grounded entities rather than fabricated strings; its percentages are proposals, not our measured quality. Current format research already separates field retention from semantic subject correctness.',
    'criteria': 'Every answer must report the observed value/absence/redaction in the requested language, attribute it correctly, and claim no new write. Retaining the literal alone is not a semantic pass. A variant is not adopted on isolated names or by suppressing bad answers.',
    'limits': {'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768, 'request_seconds': 40},
    'model': str(model), 'model_sha256': sha(model), 'backend_sha256': sha(config['llama_server']),
    'source_sha256': sha(root / 'src/baxy_mind/llm.py'), 'manifest_sha256': sha(manifest), 'private': str(private)}
assert prereg['model_sha256'] == '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
os.environ.update(BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private / 'compose-audit.jsonl'), BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')

class Measured(LlmRuntime):
    case = None
    def _post(self, payload, *args, **kwargs):
        if self.case and self.first:
            self.first = False
            if self.variant == 'baseline' and 'reference' in self.case:
                assert payload == self.case['reference']
        response = super()._post(payload, *args, **kwargs)
        with (private / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'id': self.case['id'] if self.case else None,
                                     'variant': getattr(self, 'variant', None), 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
        return response

client = Measured()
gpu, ram = ProcessTreeGpuSampler(os.getpid()), RamSampler(os.getpid())
stop = threading.Event()
violations = []
complete = False
started = time.monotonic()
def guard():
    while not stop.wait(0.25):
        if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
            violations.append('owned_gpu_conservative_bound')
        if psutil.virtual_memory().available < 768 * 2**20:
            violations.append('system_free_ram_bound')
        if violations:
            client.close()
            return
watch = threading.Thread(target=guard, daemon=True)
try:
    gpu.start()
    ram.start()
    watch.start()
    client.start_warmup()
    assert client.wait_warmup(90)
    assert gpu.telemetry_available and gpu.peak_mib is not None
    (out / 'command.json').write_text(json.dumps(client._server_command(), indent=2) + '\n', encoding='utf-8')
    for case in cases:
        for variant in ['baseline', 'retain-value']:
            client.case, client.variant, client.first = case, variant, True
            before = time.monotonic()
            client.begin_request(40)
            try:
                answer = client.compose_user_message(case['request'], 'status', facts(case, variant))
                error = None
            except (RuntimeError, TimeoutError) as exc:
                answer, error = None, str(exc)
            finally:
                client.end_request()
            row = {'id': case['id'], 'variant': variant, 'request': case['request'],
                   'answer': answer, 'error': error, 'seconds': round(time.monotonic() - before, 3)}
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
    resources = {'completed': complete, 'violations': violations, 'gpu_peak_mib': gpu.peak_mib,
                 'gpu_telemetry_available': gpu.telemetry_available, 'ram_peak_mib': ram.peak_mib,
                 'seconds': round(time.monotonic() - started, 3), 'manifest_unchanged': sha(manifest) == prereg['manifest_sha256']}
    (out / 'resources.json').write_text(json.dumps(resources, indent=2) + '\n', encoding='utf-8')
assert complete and not violations and resources['manifest_unchanged']
