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
OUT=ROOT/'artifacts/comprobaciones/C03/astra-knowledge-one-sentence';OUT.mkdir(exist_ok=False)
source=json.loads((ROOT/'artifacts/comprobaciones/C03/astra-real-users-contracts22/CASES.json').read_text(encoding='utf-8'))['development']
cases=[{'id':r['id'],'text':r['text_literal'],'source_references':r['source_references'],'language':'es'} for r in (source[3],source[4],source[5])]
cases += [{'id':'synthetic-en-definition','text':'What is an SSID?','language':'en','source_references':[]}, {'id':'synthetic-detail-control','text':'Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.','language':'es','source_references':[]}]
old_policy='un máximo de cuatro frases, salvo que la persona pida un formato concreto.'
new_policy='una frase, salvo que la persona pida profundizar, detalle o un formato concreto.'
prompt={'change':{'old':old_policy,'new':new_policy},'method':'Only the knowledge-turn policy changes; all system identity, language, context, budgets, sampling and validation remain identical.'}
reg=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json';config=json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
prereg={'cases':cases,'stages':['brief_by_request'],'prompt':prompt,
    'method':'Five BAXY chat calls: three consumed literal corpus inputs plus two labeled synthetic regression controls. No-history knowledge, temperature0 matching the product caller. Compare with the retained current baseline in astra-knowledge-brief-policy; one-sentence default with explicit depth/format exception; no effect tools, no source or registered runtime change.',
    'sourceSha256':hashlib.sha256((ROOT/'src/baxy_mind/llm.py').read_bytes()).hexdigest(),'registrationSha256':hashlib.sha256(reg.read_bytes()).hexdigest()}
(OUT/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
class Client(LlmRuntime):
    stage='';case=''
    def _post(self,payload,*args,**kwargs):
        if self.stage=='brief_by_request':
            payload=json.loads(json.dumps(payload))
            for message in payload['messages']:
                if message['role']=='system':message['content']=message['content'].replace(old_policy,new_policy)
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
                answer=client.chat(case['text'],history=[],conversation_kind='knowledge',response_language=case['language'],temperature=0.0)[0]
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
