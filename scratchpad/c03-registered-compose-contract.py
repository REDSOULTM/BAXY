"""Target the captured clock/choice failures, using native registered Qwen settings."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler
OUT=ROOT/'artifacts/comprobaciones/C03/astra-registered-compose-contract'
OUT.mkdir(exist_ok=False)
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(manifest.read_text(encoding='utf-8-sig'))
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):del os.environ[key]
# Direct LlmRuntime has no manifest loader: resolve exactly the registered fields,
# as the shell does. No model/KV/sampling alternative or prompt instrumentation.
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(OUT/'compose-audit.jsonl'),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')
cases=[]
for ident,request in [('clock-es','¿Qué hora es?'),('clock-mixed','Dime la hora, please, en spanglish'),('clock-en','What time is it?')]:
    cases.append({'id':ident,'request':request,'intent':'status','situation':{'kind':'operation','operation':'system.time','polarity':'success','verified':True,'succeeded':True,'observed':{'utc':'2026-09-06T19:09:00Z','localUtcOffsetMinutes':-180}},'expected':'16:09 or 4:09 with PM, no invented event'})
for language,request in [('es','Continúa con la recuperación de memoria.'),('en','Continue the memory recovery.'),('mixed','Continúa con la memory recovery, please.')]:
    cases.append({'id':'memory-'+language,'request':request,'intent':'confirmation','situation':{'kind':'confirmation','polarity':'pending','cause':'memory_recovery_pending','choices':['continuar','continue','cancelar','cancel'],'category':'memory_erase'},'expected':'Offer continue and cancel without claiming memory was deleted or recovered'})
for language,request in [('es','Continúa con el ajuste de volumen.'),('en','Continue the volume adjustment.'),('mixed','Continúa el volume adjustment, please.')]:
    cases.append({'id':'audio-'+language,'request':request,'intent':'confirmation','situation':{'kind':'confirmation','polarity':'pending','cause':'audio_volume_pending','choices':['continuar','continue','retry'],'level':60},'expected':'Offer continue and retry; no claim of applied volume'})
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
(OUT/'PREREG.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cases':cases,'method':'Nine direct guarded composer regression cases with the actual ModelMessageComposer.CreateFacts requiredResponseWords contract. Earlier diagnostic omitted that field and does not represent shell confirmation validation. Fixed observed clock facts replay captured16:09; recovery facts match real shell shapes. Not product effects, graphical UI or fresh acceptance. Native sampling, prompts, guards, retry budgets and registered GGUF. No hand-made drafts injected.','hashes':{str(p):sha(p) for p in [manifest,ROOT/'src/baxy_mind/llm.py',Path(__file__)]}},ensure_ascii=False,indent=2),encoding='utf-8')
class Client(LlmRuntime):
    case=None
    def _post(self,payload,*args,**kwargs):
        response=super()._post(payload,*args,**kwargs)
        with (OUT/'posts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'id':self.case['id'] if self.case else None,'payload':payload,'response':response},ensure_ascii=False)+'\n')
        return response
client=Client();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid());gpu.start();ram.start();start=time.monotonic()
try:
    client.start_warmup();assert client.wait_warmup(90)
    (OUT/'SERVER_COMMAND.json').write_text(json.dumps(client._server_command(),indent=2),encoding='utf-8')
    for case in cases:
        client.case=case;client.begin_request(40);answer=None;error=None
        try:answer=client.compose_user_message(case['request'],case['intent'],{'situation':json.dumps(case['situation'],ensure_ascii=False), 'requiredResponseWords':case['situation'].get('choices',[])})
        except Exception as exc:error=f'{type(exc).__name__}: {exc}'
        finally:client.end_request()
        row={'id':case['id'],'request':case['request'],'answer':answer,'error':error}
        with (OUT/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps(row,ensure_ascii=False),flush=True)
        assert gpu.peak_mib is None or gpu.peak_mib<=4096
finally:
    client.close();gpu.stop();ram.stop()
    result={'seconds':round(time.monotonic()-start,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib}
    (OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
