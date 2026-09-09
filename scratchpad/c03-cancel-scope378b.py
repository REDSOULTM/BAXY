"""Use guarded composition to test typed cancellation scope without source edits."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind import llm
from baxy_mind.request_reading import read_request

out = root / 'artifacts/comprobaciones/C03/astra-cancel-scope378b'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-cancel-scope378b-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
source = private.parent / 'C03-memory-product370-private'
wire = [json.loads(l) for l in (source / 'http-posts.jsonl').open(encoding='utf-8-sig')]
cases = []
for text in ['cancel', 'cancelar']:
    reference = next(r['payload'] for r in wire if r.get('stage') == 'request' and r['payload']['messages'][-1].get('content', '').startswith(text + '\nsituation:'))
    reference = copy.deepcopy(reference)
    if text == 'cancel':
        assert read_request(text).language == 'en'
        old = 'Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.'
        new = 'Mandatory language: English. Outside literal contract items, do not introduce Spanish words such as «Listo» or «encontré».'
        assert old in reference['messages'][-1]['content']
        reference['messages'][-1]['content'] = reference['messages'][-1]['content'].replace(old, new) + ' English only.'
    cases.append({'id': 'enable-' + text, 'request': text, 'operation': 'memory.enable', 'reference': reference, 'origin': 'actual370, language377'})
for label, operation, original in [('forget-en', 'memory.forget', cases[0]), ('export-es', 'memory.export', cases[1])]:
    cases.append({**copy.deepcopy(original), 'id': label, 'operation': operation, 'origin': 'synthetic operation-scope control'})
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
assert sha(model) == '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
    'method': 'Preparation378 stopped before inference because language377 also adds the existing English-only suffix; offline capture proved this was the only difference. Reference corrected for both existing language instructions. Actual LlmRuntime.compose_user_message including guards/retries on four controls. Baseline is current377 projection; first payload must equal captured370 cancellation after exactly the language correction377 for cancel. Variant only forwards the cancelledAction operation/target and marks outcome cancelled, reusing existing safe action-fact projection. No prompt, user text, model, sampler or production source change. Actual enable cancellations and two explicitly synthetic forget/export controls; no operation or effect is executed.',
    'criteria': 'State the cancellation of the specific activation/deletion/export in the request language. Do not claim memory as a whole was cancelled, the original action happened, records were deleted/exported, or another confirmation is needed. No private args, IDs or tokens; all text remains model-authored.',
    'inheritance': '370T3/T8 lack action identity. Existing remaining_steps_cancelled projection already transports cancelledAction and outcome cancelled; PrivateOperationNarration has safe pending memory action identity. Reuse those owners without a new narrative prompt.',
    'model': str(model), 'model_sha256': sha(model), 'manifest_sha256': sha(manifest), 'backend_sha256': sha(config['llama_server']), 'private': str(private)}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
original_projection = llm._compose_situation_payload
def cancellation_scope(situation, *args, **kwargs):
    payload = original_projection(situation, *args, **kwargs)
    if situation.get('cause') == 'memory_cancelled' and 'cancelledAction' in situation:
        payload['cancelledAction'] = llm._compose_action_facts(situation['cancelledAction'])
        payload['outcome'] = 'cancelled'
    return payload
class Client(llm.LlmRuntime):
    case = None
    variant = None
    first = False
    def _post(self, payload, *args, **kwargs):
        if self.first:
            self.first = False
            if self.variant == 'baseline':
                assert payload == self.case['reference'], 'baseline differs from actual product payload'
        response = super()._post(payload, *args, **kwargs)
        with (private / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'case': self.case['id'] if self.case else None, 'variant': self.variant, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
        return response
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private / 'compose-audit.jsonl'), BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')
client = Client()
try:
    client.start_warmup()
    assert client.wait_warmup(90)
    (out / 'command.json').write_text(json.dumps(client._server_command(), indent=2) + '\n', encoding='utf-8')
    for case in cases:
        for variant, projection in [('baseline', original_projection), ('cancelled-action', cancellation_scope)]:
            llm._compose_situation_payload = projection
            client.case = case
            client.variant = variant
            client.first = True
            situation = {'kind': 'status', 'polarity': 'success', 'cause': 'memory_cancelled',
                'cancelledAction': {'operation': case['operation'], 'target': 'private local memory'}}
            client.begin_request(40)
            try:
                answer = client.compose_user_message(case['request'], 'status', {'situation': json.dumps(situation, ensure_ascii=False)})
            finally:
                client.end_request()
            result = {'id': case['id'], 'variant': variant, 'answer': answer}
            with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(result, ensure_ascii=False) + '\n')
            print(json.dumps(result, ensure_ascii=True), flush=True)
finally:
    client.close()
    llm._compose_situation_payload = original_projection
assert sha(manifest) == prereg['manifest_sha256']
