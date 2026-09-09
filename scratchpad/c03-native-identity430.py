"""Compare captured native AUTO tool selection with the existing catalog-free guard."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import sys
import threading
import time
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'src')]
import psutil
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler

base=root/'artifacts/comprobaciones/C03'
local=Path(os.environ['LOCALAPPDATA'])/'BAXY'
source=local/'C03-private-product426-private'
pairs=json.loads((source/'introduction-pairs.json').read_text(encoding='utf-8'))
actual=next(p for p in pairs if p['last_user']=='Me llamo Álvaro.' and p['message'].get('tool_calls'))
reference=actual['payload']
assert reference['messages'][-1]['content']=='Me llamo Álvaro.'
cases=[
    {'id':'actual426-t5','text':'Me llamo Álvaro.','expected':'conversation','payload':reference},
]
for identifier,text in [('name-en','My name is Nina.'),('compound-name-es','Me llamo Ana María.'),('third-person','My brother is called Omar.')]:
    payload=copy.deepcopy(reference);payload['messages'][-1]['content']=text
    cases.append({'id':identifier,'text':text,'expected':'conversation','payload':payload})
wire417=[json.loads(l) for l in (local/'C03-os-product417-private/http-posts.jsonl').open(encoding='utf-8-sig')]
for i,text in enumerate(['What is my Windows username?','Con qué cuenta de Windows se está ejecutando BAXY?','Which Windows account is running BAXY?','Dime la cuenta actual de Windows.'],1):
    payload=next(r['payload'] for r in wire417 if r.get('stage')=='request' and r['payload'].get('tools') and r['payload'].get('tool_choice')=='auto' and r['payload']['messages'][-1].get('content')==text)
    cases.append({'id':f'actual417-account{i}','text':text,'expected':'system.identity','payload':payload})
for identifier,text in [('concept','What is a Windows account?'),('assistant-name','¿Cómo te llamas?'),('hypothetical','If I used another account, would Windows change my name?')]:
    payload=copy.deepcopy(cases[4]['payload']);payload['messages'][-1]['content']=text
    cases.append({'id':identifier,'text':text,'expected':'conversation','payload':payload})
out=base/'astra-native-identity430';private=local/'C03-native-identity430-private'
out.mkdir(exist_ok=False);private.mkdir(exist_ok=False)
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):os.environ.pop(name)
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(manifest.read_text(encoding='utf-8-sig'))
model=Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
os.environ.update(BAXY_MIND_LLM_GGUF=str(model),BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
prereg={'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Eleven paired native payloads. Four actual417 account primaries and actual426 introduction are exact captured requests; remaining six are synthetic last-message variations. Baseline vs only tools.function.name baxy_system__identity renamed baxy_system__windows_account. Same descriptions, arguments schema, system prompt/history/roles/weights/context/seed. Function-name mapping is diagnostic only; no source mutation, product effect, second opinion or generated-answer injection. Cold replay is not identical live scheduling; record baseline reproduction.',
 'hypothesis':'Operation description correctly says Windows account after410 but native identifier still says identity, and426/427 map self-introductions to it. Test semantic precision of the existing wire identifier before adding any speech-act grammar. Canonical kernel operation stays system.identity; no catalog/journal rename, new operation, model promotion or phrase alias.',
 'criteria':'Three self introductions and third-person fact yield conversation without claimed persistence/PC reads, four explicit accounts select same canonical read, concept/assistant/hypothetical remain conversation. Compare individual failures, including known baseline417T3 recital. No source adoption on exchanged failures. Native name mechanics in exact b9980 function-calling.md; semantic effect is unproven until measured.',
 'cases':[{'id':c['id'],'text':c['text'],'expected':c['expected']} for c in cases],
 'model':str(model),'model_sha256':sha(model),'backend_sha256':sha(config['llama_server']),'llm_source_sha256':sha(root/'src/baxy_mind/llm.py'),'manifest_sha256':sha(manifest),
 'limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'request_seconds':40},'private':str(private)}
assert prereg['model_sha256']=='00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
class Observed(LlmRuntime):
    case='';role=''
    def _post(self,payload,*args,**kwargs):
        response=super()._post(payload,*args,**kwargs)
        with (private/'posts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'id':self.case,'role':self.role,'payload':payload,'response':response},ensure_ascii=False)+'\n')
        return response
client=Observed();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid())
stop=threading.Event();violations=[];complete=False;started=time.monotonic()
def watch():
    while not stop.wait(.25):
        if gpu.peak_mib is not None and gpu.peak_mib>=3800:violations.append('gpu_bound')
        if psutil.virtual_memory().available<768*2**20:violations.append('system_free_ram_bound')
        if violations:client.close();return
guard=threading.Thread(target=watch,daemon=True)
try:
    gpu.start();ram.start();guard.start();client.start_warmup();assert client.wait_warmup(90)
    (out/'command.json').write_text(json.dumps(client._server_command(),indent=2)+'\n',encoding='utf-8',newline='\n')
    for case in cases:
        for role in ['baseline','windows-account-name']:
            payload=copy.deepcopy(case['payload'])
            old_names=[t['function']['name'] for t in payload['tools']]
            assert 'baxy_system__identity' in old_names
            if role!='baseline':
                for tool in payload['tools']:
                    if tool['function']['name']=='baxy_system__identity':tool['function']['name']='baxy_system__windows_account'
            if role=='baseline':assert payload==case['payload']
            row={'id':case['id'],'text':case['text'],'variant':role,'expected':case['expected']}
            client.case=case['id'];client.role=role;before=time.monotonic();client.begin_request(40)
            try:
                response=client._post(payload);result=(response.get('choices') or [{}])[0]
                row['native_message']=result.get('message');row['finish_reason']=result.get('finish_reason')
            except Exception as error:row['error']=type(error).__name__+':'+str(error)
            finally:client.end_request()
            row['seconds']=round(time.monotonic()-before,3)
            with (out/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps(row,ensure_ascii=True),flush=True)
            if violations:break
        if violations:break
    complete=not violations
finally:
    stop.set();client.close();guard.join(timeout=5);gpu.stop();ram.stop()
    result={'completed':complete,'violations':violations,'gpu_peak_mib':gpu.peak_mib,'ram_peak_mib':ram.peak_mib,'seconds':round(time.monotonic()-started,3),'manifest_unchanged':sha(manifest)==prereg['manifest_sha256']}
    (out/'resources.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
assert complete and result['manifest_unchanged']
