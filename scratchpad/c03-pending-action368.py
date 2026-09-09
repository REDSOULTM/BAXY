"""Second contrast: reuse the existing complete confirmation facts after an invalid reply."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind.llm import LlmRuntime

out = root / 'artifacts/comprobaciones/C03/astra-pending-action368'
out.mkdir(exist_ok=False)
base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private = base / 'C03-pending-action368-private'
private.mkdir(exist_ok=False)
source = base / 'C03-memory-product366-private'
audits = [json.loads(l) for l in (source / 'compose-audit.jsonl').open(encoding='utf-8-sig')]
wire = [json.loads(l) for l in (source / 'http-posts.jsonl').open(encoding='utf-8-sig')]
cases = []
for trace in ['t1', 't2', 't6', 't7']:
    audit = next(r for r in audits if r.get('trace') == trace and r.get('stage') == 'first' and r.get('intent') == 'confirmation')
    fragment = '\nsituation: ' + json.dumps(audit['payload'], ensure_ascii=False)
    reference = next(r['payload'] for r in wire if r.get('stage') == 'request' and any(fragment in m.get('content', '') for m in r['payload']['messages']))
    cases.append({'id': trace, 'situation': json.loads(audit['situation']), 'reference': reference})
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
assert sha(model) == '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
prereg = {
    'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
    'method': 'Replay four actual366 confirmation first payloads on the same diagnostic Qwen3.5. One difference from actual366: reuse the complete existing initial confirmation facts, including memory_enable cause and pendingAction.367 restored scope but Spanish still echoed the question; this checks the established initial narration before any source edit. Initial t1/t6 already contain this fact and are unchanged controls; invalid-reply t2/t7 acquire it. No language, prose rule, sampler, user message or source change. Only native completions; no effects or acceptance promotion.',
    'inheritance': 'PrivateOperationNarration.PendingMemoryAction already shipped344; actual366 audit demonstrates absent fact in MemoryTurnSession Invalid. Retain INVESTIGACION_FORMATO_Y_CLASIFICACION and measured operation-scope352/353; no provenance annotations or new prompt.',
    'criteria': 'Explain enabling private local memory as the pending action, invite exactly confirm/cancel, preserve English/Spanish, never assert already enabled or saved. Initial controls retain that behavior. No private arguments/IDs/tokens in payload. Product replay and owner tests required before adoption is accepted.',
    'model': str(model), 'model_sha256': sha(model), 'manifest_sha256': sha(manifest),
    'backend_sha256': sha(config['llama_server']), 'private': str(private),
}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
client = LlmRuntime()
try:
    client.start_warmup()
    assert client.wait_warmup(90)
    (out / 'command.json').write_text(json.dumps(client._server_command(), indent=2) + '\n', encoding='utf-8')
    for case in cases:
        for variant in ['baseline', 'pending-action']:
            payload = copy.deepcopy(case['reference'])
            if variant == 'pending-action':
                message = payload['messages'][-1]
                line = next(l for l in message['content'].splitlines() if l.startswith('situation: '))
                facts = json.loads(line.removeprefix('situation: '))
                facts['pendingAction'] = {'operation': 'memory.enable', 'target': 'private local memory'}
                facts['cause'] = 'memory enable'
                message['content'] = message['content'].replace(line, 'situation: ' + json.dumps(facts, ensure_ascii=False), 1)
            client.begin_request(40)
            try:
                response = client._post(payload)
            finally:
                client.end_request()
            result = {'id': case['id'], 'variant': variant, 'answer': response['choices'][0]['message'].get('content'), 'finish_reason': response['choices'][0]['finish_reason'], 'payload_unchanged': payload == case['reference']}
            with (private / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({**result, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
            with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(result, ensure_ascii=False) + '\n')
            print(json.dumps(result, ensure_ascii=True), flush=True)
finally:
    client.close()
assert sha(manifest) == prereg['manifest_sha256']
