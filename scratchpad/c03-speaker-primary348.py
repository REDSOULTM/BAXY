"""Isolate who-speaks comprehension before changing another result representation."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import json
import os
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind.llm import LlmRuntime

out=root/'artifacts/comprobaciones/C03/astra-speaker-primary348'
out.mkdir(exist_ok=False)
base=Path(os.environ['LOCALAPPDATA'])/'BAXY'
private=base/'C03-speaker-primary348-private'
private.mkdir(exist_ok=False)
previous=json.loads((root/'artifacts/comprobaciones/C03/astra-private-roles347/PREREG.json').read_text(encoding='utf-8'))
cases=[copy.deepcopy(case) for case in previous['cases'] if case['situation']['operation']=='memory.recall']
declarations={
    'memory.recall':'me llamo emmanuel, dime hola emmanuel',
    'name-lina':'Me llamo Lina.',
    'name-accent':'Me llamo Álvaro.',
    'name-english':'My name is Taylor.',
    'sister':'Mi hermana se llama Olivia.',
}
for case in cases: case['declaration']=declarations[case['id']]
for identifier,request,parent in [
    ('assistant-es','cómo te llamas',0),
    ('both-es','dime quién eres tú y quién soy yo',0),
    ('assistant-en','What is your name?',3),
]:
    case=copy.deepcopy(cases[parent])
    case.update(id=identifier,request=request)
    original=case['reference']['messages'][-1]['content']
    case['reference']['messages'][-1]['content']=request+'\nsituation: '+original.split('\nsituation: ',1)[1]
    cases.append(case)
prereg={'utc':datetime.now(timezone.utc).isoformat(),'method':'Eight speaker controls. Current fact-based native composition reference versus primary native dialogue with the same system identity and sampling, the human declaration in its own user role and the final question in a user role. No fabricated assistant message, operation, model response injection, promotion or code change. First-completion-only diagnostic: dialogue is an independent linguistic control, not an equivalent pipeline replacement. Three additional self/both-identity controls are explicitly synthetic. The owner declaration and request in memory.recall are literal recovered messages; all other names/declarations are synthetic development data.','hypothesis':'After346/347 fail to repair attribution, establish whether the exact native model understands speaker/third-party references when provenance is explicit in user dialogue. Compare with loss of provenance in label/value data; do not add a third transport variant or phrase veto before this result.','criteria':'The user is the declared person, BAXY remains the assistant, sister is Olivia. Preserve attribution, never say the assistant has the saved user name.','cases':cases,'private':str(private)}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(manifest.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):os.environ.pop(name)
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
client=LlmRuntime()
try:
    client.start_warmup();assert client.wait_warmup(90)
    (out/'SERVER_COMMAND.json').write_text(json.dumps(client._server_command(),indent=2)+'\n',encoding='utf-8')
    for case in cases:
        for variant in ['facts-reference','native-dialogue']:
            payload=copy.deepcopy(case['reference'])
            if variant=='native-dialogue':
                payload['messages']=[payload['messages'][0],{'role':'user','content':case['declaration']},{'role':'user','content':case['request']}]
            client.begin_request(40)
            try:response=client._post(payload)
            finally:client.end_request()
            result={'id':case['id'],'variant':variant,'answer':response['choices'][0]['message'].get('content'),'finish_reason':response['choices'][0]['finish_reason']}
            with (private/'posts.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps({**result,'payload':payload,'response':response},ensure_ascii=False)+'\n')
            with (out/'replies.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(result,ensure_ascii=False)+'\n')
            print(json.dumps(result,ensure_ascii=True),flush=True)
finally:client.close()
