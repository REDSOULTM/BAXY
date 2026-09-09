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
added=set()
with (local/'C03-memory-redaction443-private/posts.jsonl').open(encoding='utf-8-sig') as f:
    for line in f:
        row=json.loads(line)
        if row['variant']=='baseline' and row['id'] in {'redacted-es','redacted-en','mixed-es'} and row['id'] not in added:
            added.add(row['id']);cases.append({'id':row['id'],'payload':row['payload'],'origin':'exact443 baseline native protected/mixed record'})
assert len(cases)==11
out=base/'astra-memory-gemma444';private=local/'C03-memory-gemma444-private'
out.mkdir(exist_ok=False);private.mkdir(exist_ok=False)
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(manifest.read_text(encoding='utf-8-sig'))
model=Path('D:/BAXYRuntime/experiments/models/baxy-gemma4-e2b-published-f9b84ecd/gemma-4-E2B-it-Q4_K_M.gguf')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model),BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
prereg={'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Eleven identical first-native payloads:8baseline438 plus3protected/mixed baseline443. Only GGUF changes to the existing published BAXY Gemma E2B asset. Native model template, unchanged inputs/sampler/output allowance and ngl99/KVq8_0/cache0/no-mmap. No separate adapter, source edits, offered tools/effects or manifest change. Composition diagnostic, not integrated/fresh acceptance.',
 'new_evidence':'Qwen4B/9B both fail attribution with current memory data; feedback and representation probes rejected438–443. Existing Gemma comparison covered other responsibilities and older prompts, so preserve its rejection while measuring this new target. Reuse its exact verified published GGUF/hash; official family card/system support rechecked2026-09-08 at https://huggingface.co/google/gemma-4-E2B-it. Card does not certify this published checkpoint.',
 'criteria':'All11 useful with correct subject/values/redaction, no extra effects or false access denial; every finish reason reviewed. All8 original controls remain explicit and three protected cases cannot be omitted. GPU3800MiB/freeRAM768MiB watchdog retained; resource absence blocks success. No promotion on native alone: guarded composition and product/regression/installed profile required.',
 'cases':[{'id':c['id'],'origin':c['origin'],'request':c['payload']['messages'][-1]['content'].splitlines()[0]} for c in cases],
 'model_sha256':sha(model),'backend_sha256':sha(config['llama_server']),'manifest_sha256':sha(manifest),
 'llm_source_sha256':sha(root/'src/baxy_mind/llm.py'),
 'limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'request_seconds':40},'private':str(private)}
assert prereg['model_sha256']=='9d4a5a653f2733a5faeb5f58a0e30bc064dfd569b0059cabb2547dbc4ba0f4b7'
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
        for variant in ['published-gemma']:
            payload=copy.deepcopy(case['payload'])
            assert payload==case['payload']
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
