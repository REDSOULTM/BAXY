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

out = root / 'artifacts/comprobaciones/C03/astra-introduction-context429'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-introduction-context429-private'
source = private.parent / 'C03-private-product426-private'
audit = [json.loads(line) for line in (source/'compose-audit.jsonl').open(encoding='utf-8-sig')]
wire = [json.loads(line) for line in (source/'http-posts.jsonl').open(encoding='utf-8-sig')]
row = next(r for r in audit if r['trace']=='t5' and r['stage']=='first')
payload = next(r['payload'] for r in wire if r.get('stage')=='request'
    and r['payload']['messages'][-1].get('content','').startswith('Me llamo Álvaro.\nsituation:'))
cases = [{'id':'actual426-t5','request':'Me llamo Álvaro.','situation':json.loads(row['situation']),
    'reference':payload,'origin':'synthetic development426T5; captured wrong Windows-account composition'}]
for identifier,request in [('name-en','My name is Nina.'),('compound-name','Mi nombre es Ana María.'),('hyphenated-name','My name is Jean-Luc.')]:
    case=copy.deepcopy(cases[0]);case.pop('reference');case.update(id=identifier,request=request,origin='synthetic standalone declaration under existing declared-name grammar');cases.append(case)

prior_posts=[json.loads(l) for l in (private.parent/'C03-introduction-context428-private/posts.jsonl').open(encoding='utf-8')]
for case in cases:
    if case['id']=='actual426-t5':
        case['reference']=next(p['payload'] for p in prior_posts if p['id']==case['id'] and p['variant']=='session-context')
    else:
        case.pop('reference',None)

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def facts(case, variant):
    situation = {'kind':'status','polarity':'success','cause':'session_context_only'} if variant=='baseline' else {
        'kind':'conversation','polarity':'success'}
    return {'situation':json.dumps(situation,ensure_ascii=False)}


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
        assert payload == self.reference, 'reconstructed baseline differs from captured426'
        raise Captured()

offline = Offline()
try:
    for case in [c for c in cases if 'reference' in c]:
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
prereg = {'utc':datetime.now(timezone.utc).isoformat(),
    'cases':[{'id':c['id'],'request':c['request'],'origin':c['origin']} for c in cases],
    'method':'Existing guarded composition: existing428 session_context_only status vs existing conversation event/intent for four standalone synthetic declarations. Actual baseline must equal captured428 status payload offline and live. One conceptual change: existing conversation event and intent replaces task-status event and intent; no prompt/weights/sampler/source change. Proposed state assumes the existing typed parser proves an entire standalone declaration; this assumption requires boundary tests before implementation.428status only2/4useful, no adoption; this tests correct conversational route. No product effects or persistence.',
    'criteria':'Acknowledge the human name/current conversation, no Windows account, no claim to change persistent memory or rename BAXY. All four variants useful before source; baseline errors remain preserved. No fresh human acceptance/UI/voice.',
    'inheritance':'DeclaredNameInputPattern and public-clause split/TryBindSaveInput already exist; SessionContextOnly already emits this fact in MainWindow. No new name pattern or response.427 blanket semantic guard rejected9/13,413/414earlyread also rejected; neither reintroduced.',
    'limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'request_seconds':40},
    'model':str(model),'model_sha256':sha(model),'backend_sha256':sha(config['llama_server']),
    'source_sha256':sha(root/'src/baxy_mind/llm.py'),'manifest_sha256':sha(manifest),'private':str(private)}
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
        for variant in ['baseline', 'conversation']:
            client.case, client.variant, client.first = case, variant, True
            before = time.monotonic()
            client.begin_request(40)
            try:
                answer = client.compose_user_message(case['request'], 'status' if variant=='baseline' else 'conversation', facts(case, variant))
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
