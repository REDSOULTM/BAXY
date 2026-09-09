"""Actual compositor/model replay of the word-clock contradiction; historical facts only."""
from pathlib import Path
import hashlib,json,os,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler
OUT=ROOT/'artifacts/comprobaciones/C03/astra-word-clock-replay'
assert not OUT.exists();OUT.mkdir()
model='D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
adapter='D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f/c03-pilot-lora-v2-f32.gguf'
os.environ.update(BAXY_MIND_LLM_GGUF=model,BAXY_MIND_LLAMA_SERVER='D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe',BAXY_MIND_NGL='99',BAXY_MIND_KV_CACHE_TYPE='q8_0',
 BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(OUT/'compose-audit.jsonl'),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')
cases=[{'id':'injected-contradiction','request':'Dime la hora, please, en spanglish','injected':'Son las tres y veintitres; it’s 13:23.'},
       {'id':'es','request':'¿Qué hora es?'},{'id':'en','request':'What time is it?'},
       {'id':'mixed','request':'Dime la hora, please, en spanglish'}]
facts={'situation':json.dumps({'kind':'operation','operation':'system.time','polarity':'success','verified':True,
 'observed':{'utc':'2026-09-06T16:23:50Z','localUtcOffsetMinutes':-180}})}
(OUT/'PREREG.json').write_text(json.dumps({'kind':'compositor-replay-with-one-injected-draft-not-acceptance','cases':cases,'facts':facts,
 'scope':'Historical verified clock replay, no fresh PC observation. First case injects the exact bad prior draft, subsequent calls use the actual local model.',
 'llmSha256':hashlib.sha256((ROOT/'src/baxy_mind/llm.py').read_bytes()).hexdigest(),'model':model,'adapter':adapter},ensure_ascii=False,indent=2),encoding='utf-8')
class Replay(LlmRuntime):
    injected=None
    def _server_command(self):return super()._server_command()+['--lora',adapter]
    def _post(self,payload,*args,**kwargs):
        payload=dict(payload,temperature=.7,top_p=.8,top_k=20,min_p=0)
        if self.injected:
            text=self.injected;self.injected=None
            response={'choices':[{'message':{'content':text},'finish_reason':'stop'}]}
            injected=True
        else:
            response=super()._post(payload,*args,**kwargs);injected=False
        with (OUT/'posts.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps({'case':self.case,'injected':injected,'payload':payload,'response':response},ensure_ascii=False)+'\n')
        return response
client=Replay();gpu=ProcessTreeGpuSampler(os.getpid());gpu.start();started=time.monotonic()
try:
    client.start_warmup();assert client.wait_warmup(60)
    for case in cases:
        if gpu.peak_mib is not None and gpu.peak_mib>4096:raise RuntimeError('GPU ceiling exceeded')
        client.case=case['id'];client.injected=case.get('injected');client.begin_request(30)
        response=None;error=None
        try:response=client.compose_user_message(case['request'],'status',dict(facts,traceId=case['id']))
        except Exception as exc:error=f'{type(exc).__name__}: {exc}'
        finally:client.end_request()
        row={'case':case['id'],'request':case['request'],'response':response,'error':error}
        with (OUT/'replies.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps(row,ensure_ascii=True),flush=True)
finally:
    client.close();gpu.stop()
    result={'elapsedSeconds':round(time.monotonic()-started,2),'gpuPeakMiB':gpu.peak_mib}
    (OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
