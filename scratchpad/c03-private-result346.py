"""Compare shell status metadata with the existing verified operation envelope."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import sys
import time

root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'src'),str(root)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

out=root/'artifacts/comprobaciones/C03/astra-private-result346'
out.mkdir(exist_ok=True)
assert not (out/'PREREG.json').exists()
base=Path(os.environ['LOCALAPPDATA'])/'BAXY'
private=base/'C03-private-result346-private'
private.mkdir(exist_ok=True)
assert not (private/'posts.jsonl').exists()
source=base/'C03-memory-product345-private'
audits=[json.loads(line) for line in (source/'compose-audit.jsonl').read_text(encoding='utf-8').splitlines()]
posts=[json.loads(line) for line in (source/'http-posts.jsonl').read_text(encoding='utf-8').splitlines()]
cases=[]
for operation,request in [('memory.enable','confirmar'),('memory.save','confirmar'),('memory.recall','cómo me llamo')]:
    row=next(row for row in audits if row.get('stage')=='first' and
        json.loads(row.get('situation') or '{}').get('operation')==operation and
        json.loads(row.get('situation') or '{}').get('polarity')=='success')
    reference=None
    for post in posts:
        if post.get('stage')!='request': continue
        for message in post['payload']['messages']:
            if message['role']=='user' and ('\nsituation: '+json.dumps(row['payload'],ensure_ascii=False)) in message['content']:
                reference=post['payload']
                request=message['content'].split('\nsituation: ',1)[0]
                break
        if reference is not None: break
    assert reference is not None, operation
    cases.append({'id':operation,'request':request,'situation':json.loads(row['situation']),'reference':reference,'expected':'Report only verified memory facts; preserve the person as owner of their name.'})
for identifier,request,label,value in [
    ('name-lina','cómo me llamo','name','Lina'),
    ('name-accent','¿Cuál es mi nombre?','name','Álvaro'),
    ('name-english','What is my name?','name','Taylor'),
    ('sister','¿Cómo se llama mi hermana?','sister_name','Olivia'),
]:
    case=copy.deepcopy(cases[2])
    case.update(id=identifier,request=request,reference=None)
    case['situation']['observed']['records']=[{'label':label,'value':value}]
    cases.append(case)
case=copy.deepcopy(cases[0])
case.update(id='disabled-control',request='desactiva la memoria',reference=None)
case['situation']['operation']='memory.disable'
case['situation']['observed']['enabled']=False
cases.append(case)

manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(manifest.read_text(encoding='utf-8-sig'))
def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
pins={str(path):sha(path) for path in [manifest,root/'src/baxy_mind/llm.py',root/'src/Baxy.App/MemoryOperationResponseProjection.cs',Path(__file__)]}
prereg={'utc':datetime.now(timezone.utc).isoformat(),'method':'Eight development cases, each baseline345 versus the existing Core verified-operation envelope with the same observed facts. Three exact captured first requests must match baseline HTTP byte-for-byte as JSON objects. Five synthetic attribution/polarity controls declared. A single representation change: kind=operation and no redundant status cause, matching the journal Core result. No model/sampler/prompt/guard edit, no operation effects, no promotion. Native local composer then complete product if evidence improves. Not UI/voice/fresh acceptance.','hypothesis':'Private operation results were rebuilt as shell status and thereby acquire generic completion narration and translated status codes; retain the established operation result envelope instead. A measured question-speaker fix303–307 already works for account reads with observed-only payload. Carter_v2 LLM_CONTEXT_MEMORY_REPORT.md forbids assigning user facts to assistant identity. Reuse exact2507/template research in INVESTIGACION_MODELO_C03.md; no backend change.','criteria':'Read every first/retry/publication. Name the saved person in second person, sister in third person, enabled/disabled accurately, no system audit or unrelated effects. Preservation of records alone is insufficient.','cases':cases,'pins':pins,'private':str(private)}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'): os.environ.pop(name)
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private/'compose-audit.jsonl'),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')
class Client(LlmRuntime):
    case=None
    variant=None
    first=False
    def _post(self,payload,*args,**kwargs):
        if self.first:
            self.first=False
            if self.variant=='baseline' and self.case['reference'] is not None:
                assert payload==self.case['reference'], 'Not the captured baseline request'
        response=super()._post(payload,*args,**kwargs)
        with (private/'posts.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps({'case':self.case['id'] if self.case else None,'variant':self.variant,'payload':payload,'response':response},ensure_ascii=False)+'\n')
        return response
client=Client()
gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid())
gpu.start();ram.start();start=time.monotonic()
try:
    client.start_warmup();assert client.wait_warmup(90)
    (out/'SERVER_COMMAND.json').write_text(json.dumps(client._server_command(),indent=2)+'\n',encoding='utf-8')
    for case in cases:
        for variant in ['baseline','operation']:
            situation=copy.deepcopy(case['situation'])
            if variant=='operation':
                situation['kind']='operation'
                situation.pop('cause')
            client.case=case;client.variant=variant;client.first=True
            client.begin_request(40)
            answer=None;error=None
            try: answer=client.compose_user_message(case['request'],'status',{'situation':json.dumps(situation,ensure_ascii=False)})
            except AssertionError: raise
            except Exception as exc: error=f'{type(exc).__name__}: {exc}'
            finally: client.end_request()
            result={'id':case['id'],'variant':variant,'answer':answer,'error':error}
            with (out/'replies.jsonl').open('a',encoding='utf-8') as stream: stream.write(json.dumps(result,ensure_ascii=False)+'\n')
            print(json.dumps(result,ensure_ascii=True),flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib<=4096
finally:
    client.close();gpu.stop();ram.stop()
    result={'seconds':round(time.monotonic()-start,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'manifest_unchanged':sha(manifest)==pins[str(manifest)]}
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result),flush=True)
