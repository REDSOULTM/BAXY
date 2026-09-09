"""Compare one audio instruction on inherited cases; never inject answer text."""
from pathlib import Path
import copy,datetime,hashlib,json,os,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler
BASE=ROOT/'artifacts/comprobaciones/C03';OUT=BASE/'astra-audio-wording-ablation'
OUT.mkdir(exist_ok=False)
registration=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(registration.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(OUT/'compose-audit.jsonl'),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')
cases=json.loads((BASE/'astra-compositor-ablation-qwen-base/PREREG.json').read_text(encoding='utf-8'))['cases']
for case in cases:
    case.pop('payload',None)
    situation=json.loads(case['facts']['situation'])
    if case['intent']=='confirmation':case['facts']['requiredResponseWords']=situation.get('choices',[])
    if case['intent'] in {'status','error'}:case['facts']['mustNotAskFollowUp']=True
captured=json.loads((BASE/'astra-registered-integrated-qwen/paired.json').read_text(encoding='utf-8'))[1]
source=next(c['situation'] for c in captured['compose'] if c.get('situation'))
for muted in [False,True]:
    for language,request in [('es',captured['request']),('en','Tell me the time and audio state.'),('mixed','Dime la hora and the audio status, please.')]:
        fact=json.loads(source)
        fact['completedRequest']=request
        fact['observed']['muted']=muted
        steps=[]
        for step in fact['steps']:
            d=json.loads(step)
            if d.get('operation')=='audio.status':d['observed']['state']['muted']=muted
            steps.append(json.dumps(d,ensure_ascii=False))
        fact['steps']=steps
        cases.append({'id':f'captured-audio-{muted}-{language}','route':'mission-summary','request':request,'language':language,'intent':'status','facts':{'situation':json.dumps(fact,ensure_ascii=False),'mustNotAskFollowUp':True}})
old='Name mute state.';new='Describe whether sound is silenced.'
prereg={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cases':cases,'variants':['baseline','audio_instruction'],'change':{'before':old,'after':new},'method':'Thirty consumed/inherited direct cases (24 eight-route cases plus six captured-state clock/audio contrasts). Synthetic states, not new PC effects or fresh acceptance. Native registered model/cache/sampling and guards. Only candidate instruction text changes, after normal prompt construction; user text/facts untouched. Correct shell requiredResponseWords contract included. Baseline repeated for actual comparison; no product edit yet.','sourceSha256':hashlib.sha256((ROOT/'src/baxy_mind/llm.py').read_bytes()).hexdigest(),'registrationSha256':hashlib.sha256(registration.read_bytes()).hexdigest()}
(OUT/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
class Client(LlmRuntime):
    variant='baseline';case=None
    def _post(self,payload,*args,**kwargs):
        payload=copy.deepcopy(payload)
        if self.variant=='audio_instruction':
            for message in payload['messages']:message['content']=message['content'].replace(old,new)
        response=super()._post(payload,*args,**kwargs)
        with (OUT/'posts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'variant':self.variant,'id':self.case['id'] if self.case else None,'payload':payload,'response':response},ensure_ascii=False)+'\n')
        return response
client=Client();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid());gpu.start();ram.start();start=time.monotonic()
try:
    client.start_warmup();assert client.wait_warmup(90)
    for variant in prereg['variants']:
        client.variant=variant
        for case in cases:
            client.case=case;client.begin_request(40);answer=None;error=None
            try:
                if case['route']=='conversation':answer=client.chat(case['request'],conversation_kind='knowledge',response_language=case['language'])[0]
                else:answer=client.compose_user_message(case['request'],case['intent'],case['facts'])
            except Exception as exc:error=f'{type(exc).__name__}: {exc}'
            finally:client.end_request()
            row={'variant':variant,'id':case['id'],'request':case['request'],'answer':answer,'error':error}
            with (OUT/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps(row,ensure_ascii=False),flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib<=4096
finally:
    client.close();gpu.stop();ram.stop()
    result={'seconds':round(time.monotonic()-start,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib}
    (OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
