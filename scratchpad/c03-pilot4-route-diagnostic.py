"""Eight response routes against explicitly synthetic facts; no PC effects or acceptance claims."""
from pathlib import Path
import hashlib,json,os,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler
OUT=ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot4-routes'
BASE=Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f')
MODEL=Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf')
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
cases=[]
def add(route,intent,questions,situation,criteria):
    for lang,question in zip(['es','en','mixed'],questions):
        s=dict(situation)
        if route=='confirmation':
            s.update(pendingRequest=question,pendingAction={'operation':'app.close','purpose':question,'arguments':{'title':'Panel local C03','windowId':'synthetic-window'}})
        if route=='mission-summary':s['completedRequest']=question
        cases.append({'id':route+'-'+lang,'route':route,'language':lang,'request':question,'intent':intent,
                      'facts':{'situation':json.dumps(s,ensure_ascii=False),'traceId':route+'-'+lang},
                      'criteria':criteria+' Requested language; no invented facts or full repeated translation.'})
add('welcome','welcome',['Hola','Hello','Hey, buenas; responde en spanglish.'],{'kind':'welcome','polarity':'success'},'Brief natural greeting; no invented user state.')
add('conversation','conversation',['¿Qué es un sinónimo?','What is a synonym?','What is a synonym? Explícalo en spanglish.'],{},'Useful explanation of similar meaning; no action claims.')
add('clarification','clarification',['Ajusta el volumen.','Set the volume.','Set the volume, por favor, en spanglish.'],
    {'kind':'clarification','polarity':'pending','cause':'missing_arguments','operation':'audio.volume','target':'volume'},
    'Ask what volume level is wanted. No guessed level, denial or claim of completion.')
add('confirmation','confirmation',['Cierra la ventana titulada Panel local C03.','Close the window titled Panel local C03.','Close la ventana titulada Panel local C03; responde en spanglish.'],
    {'kind':'confirmation','polarity':'pending','cause':'step_confirm_or_cancel','step':2,'choices':['confirmar','confirm','cancelar','cancel']},
    'Ask confirmation or cancellation for the exact named window; never say it has already closed.')
add('progress','status',['Busca las aplicaciones instaladas.','Find the installed applications.','Find las aplicaciones instaladas; responde en spanglish.'],
    {'kind':'status','polarity':'success','cause':'acting'},'Report work in progress on the requested search; no completed list or invented findings.')
add('result','status',['¿Cuál es el volumen y está silenciado?','What is the volume, and is it muted?','What is the volume y está silenciado? Responde en spanglish.'],
    {'kind':'operation','operation':'audio.status','polarity':'success','verified':True,'succeeded':True,'readOnly':True,
     'observed':{'state':{'volumePercent':46,'muted':False}}},'Read-only result: volume46%, not muted; do not claim a change.')
add('error','error',['Abre EstudioC03.','Open EstudioC03.','Open EstudioC03, por favor; responde en spanglish.'],
    {'kind':'operation','operation':'app.open','polarity':'failure','verified':True,'succeeded':False,'cause':'app_not_found','target':'EstudioC03','operationAttempted':True},
    'Opening failed because the named app was not found; do not invent installation, access denial or an opened window.')
steps=[{'kind':'operation','operation':'system.time','polarity':'success','verified':True,'succeeded':True,'readOnly':True,
        'observed':{'utc':'2026-01-01T17:42:00+00:00','localUtcOffsetMinutes':0}},
       {'kind':'operation','operation':'audio.status','polarity':'success','verified':True,'succeeded':True,'readOnly':True,
        'observed':{'state':{'volumePercent':46,'muted':False}}}]
add('mission-summary','status',['Dime la hora y el estado del audio.','Tell me the time and audio state.','Tell me la hora y el estado del audio; responde en spanglish.'],
    {'kind':'status','polarity':'success','cause':'mission_completed','steps':[json.dumps(s) for s in steps]},
    'Summary preserves 17:42, volume46%, not muted; both steps read-only, no state changes.')
assert len(cases)==24
if '--prepare-only' in sys.argv:
    assert not OUT.exists();OUT.mkdir()
    (OUT/'CASES.json').write_text(json.dumps({'kind':'synthetic-composition-diagnostic-not-integrated-acceptance','cases':cases,
      'coverage':'24 cases, eight response routes and three languages. Conversation duplicates an existing development question; not counted as fresh acceptance.',
      'noEffects':'Only chat and compose_user_message; no kernel, provider, app launch, file operation or current PC reading.'},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Prepared 24 synthetic route cases; no inference.');raise SystemExit()
assert OUT.exists() and not (OUT/'RESULT.json').exists()
assert json.loads((OUT/'CASES.json').read_text(encoding='utf-8'))['cases']==cases
os.environ.update(BAXY_MIND_LLM_GGUF=str(MODEL),BAXY_MIND_LLAMA_SERVER='D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe',BAXY_MIND_NGL='99',BAXY_MIND_KV_CACHE_TYPE='q8_0')
results=[]
class Candidate(LlmRuntime):
    def __init__(self,variant):super().__init__();self.variant=variant;self.case=None
    def _server_command(self):return super()._server_command()+['--lora',str(BASE/f'c03-pilot-lora-v{self.variant}-f32.gguf')]
    def _post(self,payload,*args,**kwargs):
        response=super()._post(payload,*args,**kwargs)
        if self.case:
            with (OUT/'posts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'variant':self.variant,'case':self.case,'payload':payload,'response':response},ensure_ascii=False)+'\n')
        return response
(OUT/'PREREG.json').write_text(json.dumps({'variants':[3,4],'hashes':{str(p):digest(p) for p in [MODEL,BASE/'c03-pilot-lora-v3-f32.gguf',BASE/'c03-pilot-lora-v4-f32.gguf',OUT/'CASES.json',ROOT/'src/baxy_mind/llm.py']},'gpuCeilingMiB':4096,'requestSeconds':40},indent=2),encoding='utf-8')
for variant in [3,4]:
    os.environ.update(BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(OUT/f'compose-audit-v{variant}.jsonl'),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')
    client=Candidate(variant);gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid());gpu.start();ram.start();started=time.monotonic();fatal=None
    try:
        client.start_warmup();assert client.wait_warmup(60)
        for case in cases:
            assert gpu.peak_mib is not None and gpu.peak_mib<=4096
            client.case=case['id'];client.begin_request(40);tick=time.monotonic();error=None;answer=None
            try:
                if case['route']=='conversation':answer=client.chat(case['request'],conversation_kind='knowledge',response_language=case['language'])
                else:answer=client.compose_user_message(case['request'],case['intent'],case['facts'])
            except Exception as exc:error=f'{type(exc).__name__}: {exc}'
            finally:client.end_request()
            row={'variant':variant,'id':case['id'],'route':case['route'],'language':case['language'],'request':case['request'],'response':answer,'error':error,'seconds':round(time.monotonic()-tick,3)}
            with (OUT/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps({'variant':variant,'case':case['id'],'error':error}),flush=True)
    except Exception as exc:fatal=f'{type(exc).__name__}: {exc}'
    finally:
        client.close();gpu.stop();ram.stop();results.append({'variant':variant,'seconds':round(time.monotonic()-started,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'error':fatal})
        (OUT/'RESULT.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(results[-1]),flush=True)
    if fatal:break
