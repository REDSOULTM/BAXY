"""Same real inputs and conversation contract, one negative-instruction policy."""
from pathlib import Path
import copy, hashlib, json, os, sys, time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler
BASE=ROOT/'artifacts/comprobaciones/C03';OUT=BASE/'astra-negative-dialogue-ablation';OUT.mkdir(exist_ok=False)
rows=json.loads((BASE/'astra-real-users-pending22/paired.json').read_text(encoding='utf-8'))
cases=[{'id':rows[i-1]['turnId'],'text':rows[i-1]['request']} for i in [3,4,5,6,11,20]]
register=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json';config=json.loads(register.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
old='Política interna del turno: conocimiento o explicación. '
new=old+'Atiende las restricciones negativas sin convertirlas en tareas ni pedir datos para abstenerte. '
prereg={'cases':cases,'variants':['baseline','negative_policy'],'change':{'before':old,'after':new},'method':'Six consumed literal real-log cases; standalone chat knowledge/es, same registered runtime/cache/sampling and normal guards. Add one general policy sentence only. No effects, synthetic input paraphrases or new acceptance.', 'registrationSha256':hashlib.sha256(register.read_bytes()).hexdigest()}
(OUT/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
class Client(LlmRuntime):
    variant=None;case=None
    def _post(self,payload,*args,**kwargs):
        payload=copy.deepcopy(payload)
        if self.variant=='negative_policy':
            for message in payload['messages']:message['content']=message['content'].replace(old,new)
        response=super()._post(payload,*args,**kwargs)
        with (OUT/'posts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'variant':self.variant,'case':self.case,'payload':payload,'response':response},ensure_ascii=False)+'\n')
        return response
client=Client();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid());gpu.start();ram.start();started=time.monotonic()
try:
    client.start_warmup();assert client.wait_warmup(90)
    for variant in prereg['variants']:
        client.variant=variant
        for case in cases:
            client.case=case['id'];client.begin_request(40);answer=None;error=None
            try:answer=client.chat(case['text'],history=[],conversation_kind='knowledge',response_language='es',temperature=0.0)[0]
            except Exception as exc:error=f'{type(exc).__name__}: {exc}'
            finally:client.end_request()
            row={'variant':variant,'id':case['id'],'text':case['text'],'answer':answer,'error':error}
            with (OUT/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps(row,ensure_ascii=False),flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib<=4096
finally:
    client.close();gpu.stop();ram.stop();result={'elapsedSeconds':round(time.monotonic()-started,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'registrationUnchanged':hashlib.sha256(register.read_bytes()).hexdigest()==prereg['registrationSha256']}
    (OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
