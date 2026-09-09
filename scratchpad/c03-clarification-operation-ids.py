"""Existing composer versus explicit constraint representation; no execution."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler
OUT=ROOT/'artifacts/comprobaciones/C03/astra-clarification-operation-ids';OUT.mkdir(exist_ok=False)
pool=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-real-user-pool-20260906/unique_requests.jsonl'
prefixes={'6035be9b29','a59b4669cb','c6408d0b4d'}
cases=[]
with pool.open(encoding='utf-8') as f:
    for line in f:
        r=json.loads(line)
        if r['id'][:10] in prefixes:
            cases.append({'id':r['id'],'text':r['text_literal'],'source_references':r['occurrences'],'language':'en' if r['id'].startswith('a59b') else 'es'})
assert len(cases)==3
prompt='Inherited formulate_explicit_clarification_question, operations audio.volume.adjust and missing_fields amount. Compare unchanged wire payload against removal of recognized_operations only.'
reg=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json';config=json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
prereg={'cases':cases,'stages':['current_clarifier','without_operation_ids'],'prompt':prompt,
    'method':'Six direct clarification calls on three literal corpus inputs, marked consumed for development; freshness/human authorship not certified. Paired original versus removal of operation identifiers from JSON data, all other messages/schema/sampling unchanged. No effects, no product promotion.',
    'sourceSha256':hashlib.sha256((ROOT/'src/baxy_mind/llm.py').read_bytes()).hexdigest(),'registrationSha256':hashlib.sha256(reg.read_bytes()).hexdigest()}
(OUT/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
class Client(LlmRuntime):
    stage='';case=''
    def _post(self,payload,*args,**kwargs):
        if self.stage=='without_operation_ids':
            payload=json.loads(json.dumps(payload))
            data=json.loads(payload['messages'][-1]['content']);data.pop('recognized_operations',None)
            payload['messages'][-1]['content']=json.dumps(data,ensure_ascii=False,separators=(',',':'))
        response=super()._post(payload,*args,**kwargs)
        with (OUT/'posts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'stage':self.stage,'case':self.case,'payload':payload,'response':response},ensure_ascii=False)+'\n')
        return response
client=Client();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid());gpu.start();ram.start();started=time.monotonic()
try:
    client.start_warmup();assert client.wait_warmup(90)
    for stage in prereg['stages']:
        client.stage=stage
        for case in cases:
            client.case=case['id'];client.begin_request(35);answer=None;error=None
            try:
                answer=client.formulate_explicit_clarification_question(case['text'],('audio.volume.adjust',),('amount',))
            except Exception as exc:error=f'{type(exc).__name__}: {exc}'
            finally:client.end_request()
            result={'stage':stage,'id':case['id'],'text':case['text'],'answer':answer,'error':error}
            with (OUT/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(result,ensure_ascii=False)+'\n')
            print(json.dumps(result,ensure_ascii=False),flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib<=4096
finally:
    client.close();gpu.stop();ram.stop()
    result={'elapsedSeconds':round(time.monotonic()-started,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'registrationUnchanged':hashlib.sha256(reg.read_bytes()).hexdigest()==prereg['registrationSha256']}
    (OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
