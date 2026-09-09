"""Current Qwen3.5 memory results in native tool-return roles, inherited347."""
from pathlib import Path
from datetime import datetime,timezone
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
base=root/'artifacts/comprobaciones/C03';local=Path(os.environ['LOCALAPPDATA'])/'BAXY'
with (local/'C03-private-product437-private/http-posts.jsonl').open(encoding='utf-8-sig') as f:
    wire=[json.loads(line) for line in f]
def fact_line(payload):
    return next(line for line in payload['messages'][-1]['content'].splitlines() if line.startswith('situation: '))
def operation_payload(operation,request=None):
    for row in wire:
        if row.get('stage')!='request':continue
        payload=row['payload'];body=payload['messages'][-1].get('content','')
        if request is not None and not body.startswith(request+'\n'):continue
        try:situation=json.loads(fact_line(payload).removeprefix('situation: '))
        except (StopIteration,json.JSONDecodeError):continue
        if situation.get('operation')==operation and situation.get('outcome')=='completed':return payload
    raise AssertionError((operation,request))
spanish=operation_payload('memory.recall','¿Qué nombre tienes guardado en tu memoria privada?')
english=operation_payload('memory.recall','What name have you saved in private memory?')
cases=[{'id':'actual437-t7','payload':spanish,'origin':'exact437 native ES recall'},
       {'id':'actual437-t4','payload':english,'origin':'exact437 native EN recall'}]
def synthetic(identifier,request,records):
    payload=copy.deepcopy(spanish);body=payload['messages'][-1]['content'];old=fact_line(payload)
    situation=json.loads(old.removeprefix('situation: '));situation['seen'].update(records=records,shown=len(records),total=len(records))
    lines=body.splitlines();lines[0]=request
    lines=[('situation: '+json.dumps(situation,ensure_ascii=False)) if line==old else ('Hechos: '+', '.join(r['value'] for r in records)) if line.startswith('Hechos: ') else line for line in lines]
    payload['messages'][-1]['content']='\n'.join(lines)
    cases.append({'id':identifier,'payload':payload,'origin':'synthetic current recall payload; literal contract updated consistently'})
synthetic('name-marta','¿Qué nombre tienes guardado en tu memoria privada?',[{'label':'name','value':'Marta'}])
synthetic('compound-name','¿Qué nombre tienes guardado en tu memoria privada?',[{'label':'name','value':'Ana María'}])
synthetic('third-person','¿Qué nombre de mi hermana tienes guardado?',[{'label':'sister.name','value':'Nina'}])
synthetic('two-records','¿Qué nombres tienes guardados en tu memoria privada?',[{'label':'name','value':'Jordan'},{'label':'sister.name','value':'Nina'}])
for operation in ['memory.enable','memory.save']:
    cases.append({'id':operation,'payload':operation_payload(operation),'origin':'exact437 completed private result control'})
out=base/'astra-memory-roles438';private=local/'C03-memory-roles438-private'
out.mkdir(exist_ok=False);private.mkdir(exist_ok=False)
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(manifest.read_text(encoding='utf-8-sig'))
model=Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model),BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
prereg={'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Eight paired native first-completion payloads. Four exact437 completed memory results; four synthetic records with matching required-fact literals. Baseline unchanged; variant moves the unchanged situation line from user body to a native tool return paired with assistant tool call, inherited347. User request and all instructions/settings are unchanged. No tools offered, no execution, no source edits, no reclassification/validation retry or promotion. Not guarded publication/UI/voice/fresh acceptance.',
 'new_evidence':'347 tool roles and349 seen.source failed under2507. Current437 is3.5, with source402 literal preservation and operation scope in actual payload. This changes the candidate and measured failure population; compare once with current capture, not a repeat on2507 or another provenance phrase.434/437 T7 value is intact but assistant subject is wrong.',
 'criteria':'No assistant-name attribution, no extra audit/state/persistence claims; values and third-party relation intact. Exact EN recall and enable/save controls must retain usefulness. Inspect every native answer and finish_reason. If roles do not improve without exchanged failures, no source adoption.',
 'cases':[{'id':c['id'],'origin':c['origin'],'request':c['payload']['messages'][-1]['content'].splitlines()[0]} for c in cases],
 'model_sha256':sha(model),'backend_sha256':sha(config['llama_server']),'manifest_sha256':sha(manifest),
 'llm_source_sha256':sha(root/'src/baxy_mind/llm.py'),
 'limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'request_seconds':40},'private':str(private)}
assert prereg['model_sha256']=='00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
client=LlmRuntime();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid())
stop=threading.Event();violations=[];complete=False;started=time.monotonic()
def watch():
    while not stop.wait(.25):
        if gpu.peak_mib is not None and gpu.peak_mib>=3800:violations.append('gpu_bound')
        if psutil.virtual_memory().available<768*2**20:violations.append('system_free_ram_bound')
        if violations:client.close();return
guard=threading.Thread(target=watch,daemon=True)
try:
    gpu.start();ram.start();guard.start();client.start_warmup();assert client.wait_warmup(90)
    (out/'command.json').write_text(json.dumps(client._server_command(),indent=2)+'\n',newline='\n')
    for case in cases:
        for variant in ['baseline','tool-return']:
            payload=copy.deepcopy(case['payload'])
            if variant=='tool-return':
                body=payload['messages'][-1]['content'];fact=fact_line(payload)
                user='\n'.join(line for line in body.splitlines() if line!=fact)
                operation=json.loads(fact.removeprefix('situation: '))['operation']
                payload['messages']=[*payload['messages'][:-1],{'role':'user','content':user},
                    {'role':'assistant','content':None,'tool_calls':[{'id':'observed_private','type':'function','function':{'name':operation,'arguments':'{}'}}]},
                    {'role':'tool','tool_call_id':'observed_private','name':operation,'content':fact}]
            else:assert payload==case['payload']
            before=time.monotonic();client.begin_request(40)
            try:
                response=client._post(payload);choice=response['choices'][0]
                row={'id':case['id'],'variant':variant,'answer':choice['message'].get('content'),'finish_reason':choice.get('finish_reason')}
                with (private/'posts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({**row,'payload':payload,'response':response},ensure_ascii=False)+'\n')
            except Exception as error:row={'id':case['id'],'variant':variant,'error':type(error).__name__+':'+str(error)}
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
    (out/'resources.json').write_text(json.dumps(result,indent=2)+'\n',newline='\n')
assert complete and result['manifest_unchanged']
