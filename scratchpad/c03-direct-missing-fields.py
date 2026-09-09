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
OUT=ROOT/'artifacts/comprobaciones/C03/astra-direct-missing-fields';OUT.mkdir(exist_ok=False)
pool=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-real-user-pool-20260906/unique_requests.jsonl'
prefixes={'6035be9b29','a59b4669cb','c6408d0b4d'}
cases=[]
with pool.open(encoding='utf-8') as f:
    for line in f:
        r=json.loads(line)
        if r['id'][:10] in prefixes:
            cases.append({'id':r['id'],'text':r['text_literal'],'source_references':r['occurrences'],'language':'en' if r['id'].startswith('a59b') else 'es'})
assert len(cases)==3
cases += [{'id':'synthetic-complete-up','text':'turn up the volume by 10%','language':'en','source_references':[]}, {'id':'synthetic-complete-down','text':'baja el volumen en 5 puntos','language':'es','source_references':[]}]
tool={'type':'function','function':{'name':'audio_volume_adjust','canonical_name':'audio.volume.adjust','description':'Sube o baja el volumen de salida una cantidad acotada desde su valor observado y verifica la postlectura.','parameters':{'type':'object','properties':{'amount':{'type':'integer','minimum':1,'maximum':100},'direction':{'type':'string','enum':['down','up']}},'required':['amount','direction'],'additionalProperties':False}}}
old_instruction='Formula fallback_question como una pregunta natural y breve para obtener estos campos: '
new_instruction='Formula fallback_question como una pregunta natural y breve para obtener sólo los datos requeridos que falten o sean ambiguos. No vuelvas a preguntar datos explícitos en el pedido. Campos requeridos de la operación: '
prompt={'inherited':'extract_direct_arguments','change':{'old':old_instruction,'new':new_instruction},'tool':tool}
reg=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json';config=json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
prereg={'cases':cases,'stages':['current_direct','missing_only'],'prompt':prompt,
    'method':'Ten direct extraction calls, three consumed literal corpus inputs plus two explicitly synthetic complete-argument controls. Paired unchanged instruction versus asking only missing/ambiguous fields. Same schema and sampling, registered assets; no effects or model/runtime promotion.',
    'sourceSha256':hashlib.sha256((ROOT/'src/baxy_mind/llm.py').read_bytes()).hexdigest(),'registrationSha256':hashlib.sha256(reg.read_bytes()).hexdigest()}
(OUT/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
class Client(LlmRuntime):
    stage='';case=''
    def _post(self,payload,*args,**kwargs):
        if self.stage=='missing_only':
            payload=json.loads(json.dumps(payload))
            assert old_instruction in payload['messages'][0]['content']
            payload['messages'][0]['content']=payload['messages'][0]['content'].replace(old_instruction,new_instruction)
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
                client._direct_argument_handoff=None
                extracted=client.extract_direct_arguments(case['text'],tool)
                answer={'arguments':extracted.arguments,'fallback_question':extracted.fallback_question}
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
