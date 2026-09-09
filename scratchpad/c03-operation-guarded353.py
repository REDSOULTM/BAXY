"""Use production composition/guards/retries for the operation-scope contrast352."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind import llm

out=root/'artifacts/comprobaciones/C03/astra-operation-guarded353'
out.mkdir(exist_ok=False)
base=Path(os.environ['LOCALAPPDATA'])/'BAXY'
private=base/'C03-operation-guarded353-private'
private.mkdir(exist_ok=False)
prior=json.loads((root/'artifacts/comprobaciones/C03/astra-operation-scope352/PREREG.json').read_text(encoding='utf-8'))
cases=prior['cases']
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(manifest.read_text(encoding='utf-8-sig'))
prereg={'utc':datetime.now(timezone.utc).isoformat(),'method':'Same nine cases352 through actual LlmRuntime.compose_user_message, preserving all guards/retries. Compare current projection with operation field forwarded from the actual typed situation. Baseline first payload must equal the captured reference as a JSON object. Both current2507 and availableQwen3.5, runtime registration unchanged; no effects, source edit or promotion. This tests guarded Python publication, still not the App/UI/product acceptance.','criteria':'Preserve enabled/saved/disabled/recall facts, scope the disabled failure to memory.save. Record every retry and never score a missing failure or ignored request as useful.352 first-completion-only left the Qwen3.5 error at Hola Emmanuel, which must be rejected and recovered by the existing guards.','cases':cases,'models':prior['models'],'private':str(private)}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
original=llm._compose_situation_payload
def with_scope(situation,*args,**kwargs):
    payload=original(situation,*args,**kwargs)
    operation=situation.get('operation')
    if isinstance(operation,str) and operation.strip():payload['operation']=operation.strip()
    return payload
class Client(llm.LlmRuntime):
    case=None
    variant=None
    model_label=None
    first=False
    def _post(self,payload,*args,**kwargs):
        if self.first:
            self.first=False
            if self.variant=='baseline':assert payload==self.case['reference'], 'Baseline differs from captured request'
        response=super()._post(payload,*args,**kwargs)
        with (private/'posts.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps({'case':self.case['id'] if self.case else None,'model':self.model_label,'variant':self.variant,'payload':payload,'response':response},ensure_ascii=False)+'\n')
        return response
try:
    for name,path in prior['models']:
        for key in list(os.environ):
            if key.startswith('BAXY_MIND_'):os.environ.pop(key)
        os.environ.update(BAXY_MIND_LLM_GGUF=path,BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private/(name+'-audit.jsonl')),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')
        client=Client();client.model_label=name
        try:
            client.start_warmup();assert client.wait_warmup(90)
            for case in cases:
                request=case['reference']['messages'][-1]['content'].split('\nsituation: ',1)[0]
                intent='error' if case['situation'].get('polarity')=='failure' else 'status'
                for variant,projection in [('baseline',original),('operation-scope',with_scope)]:
                    llm._compose_situation_payload=projection
                    client.case=case;client.variant=variant;client.first=True
                    client.begin_request(40)
                    answer=None;error=None
                    try:answer=client.compose_user_message(request,intent,{'situation':json.dumps(case['situation'],ensure_ascii=False)})
                    except AssertionError:raise
                    except Exception as exc:error=f'{type(exc).__name__}: {exc}'
                    finally:client.end_request()
                    result={'id':case['id'],'model':name,'variant':variant,'answer':answer,'error':error}
                    with (out/'replies.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(result,ensure_ascii=False)+'\n')
                    print(json.dumps(result,ensure_ascii=True),flush=True)
        finally:client.close()
finally:llm._compose_situation_payload=original
