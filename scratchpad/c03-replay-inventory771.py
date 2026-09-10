"""Tie the candidate correction request to measured770C and replay exact outputs."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from baxy_mind.llm import LlmRuntime, _compose_situation_payload, _payload_fact_defect

PRIVATE=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-correction-isolation770-private'
OUT=ROOT/'artifacts/comprobaciones/C03/INVENTORY_SCOPE771'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not (OUT/'CAPTURED_REPLAY.json').exists()
OUT.mkdir(exist_ok=True)
facts=read(PRIVATE/'reconstructed.json')
results={r['arm']:r for r in read(PRIVATE/'results.json')}
planned={r['arm']:r['payload'] for r in read(PRIVATE/'planned.json')}
model=read(ROOT/'artifacts/comprobaciones/C03/CORRECTION_ISOLATION770/PREREG.json')['model']['path']


class Recorder(LlmRuntime):
    def __init__(self, replies):
        self._gguf=model
        self.replies=iter(replies)
        self.requests=[]

    def _post(self,payload):
        self.requests.append(copy.deepcopy(payload))
        return {'choices':[{'message':{'content':next(self.replies)},'finish_reason':'stop'}]}


assert _compose_situation_payload(facts['situation'],'es',facts['user_text'])==facts['captured_payload']
checks=[]
for arm in ['C_explicit_cause','D_no_draft_explicit_cause']:
    answer=results[arm]['response']['choices'][0]['message']['content']
    client=Recorder([answer])
    actual=client.compose_user_message(facts['user_text'],'status',{'situation':facts['situation']})
    assert actual==answer and len(client.requests)==1
    checks.append({'arm':arm,'exact_captured_reply_published':True,'stub_calls':1})
answer=results['C_explicit_cause']['response']['choices'][0]['message']['content']
client=Recorder([facts['draft'],answer])
assert client.compose_user_message(facts['user_text'],'status',{'situation':facts['situation']})==answer
assert len(client.requests)==2 and client.requests[1]==planned['C_explicit_cause']
assert _payload_fact_defect(results['A_current']['response']['choices'][0]['message']['content'],facts['captured_payload'],facts['user_text'])=='extra_claim'
result={'measured770C_request_exactly_equal_to_candidate_retry':True,'checks':checks,
    'wrong_recency_still_rejected':True,'second_attempt_returns_exact_measured_C':True,
    'input_reconstructed_with_equal_projected_payload':True,'raw_product_input_byte_identity':False,
    'new_inference_calls':0,'survey_coverage_added':0,
    'source_pins':{p:sha(ROOT/p) for p in ['src/baxy_mind/llm.py','src/baxy_mind/window_prose_facts.py']},
    'evidence_sha256':{name:sha(PRIVATE/name) for name in ['results.json','planned.json','reconstructed.json']},
    'known_remaining_failure':'770B still omits one repeated identity; manual completeness fails even if the fact checker accepts. No credit from that arm.',
    'scope':'Controlled replay of exact captured outputs with reconstructed verified facts, not a new real product session. Registered regression still required.'}
(OUT/'CAPTURED_REPLAY.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
print(json.dumps(result))
