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
def fact_line(payload):
    return next(line for line in payload['messages'][-1]['content'].splitlines() if line.startswith('situation: '))
cases=[];seen=set()
with (local/'C03-required-fact401-private/posts.jsonl').open(encoding='utf-8-sig') as f:
    for line in f:
        row=json.loads(line)
        if row['variant']!='retain-value' or row['id'] in seen:continue
        seen.add(row['id'])
        cases.append({'id':row['id'],'payload':row['payload'],'origin':'exact401 first native payload with402 literal retention'})
assert len(cases)==8
redacted=next(c['payload'] for c in cases if c['id']=='redacted-es')
en=copy.deepcopy(next(c['payload'] for c in cases if c['id']=='stored-en'))
body=en['messages'][-1]['content'];old=fact_line(en)
situation=json.loads(old.removeprefix('situation: '))
situation['seen']['records']=[{'label':'secret','value':'[REDACTED]'}]
lines=body.splitlines();lines[0]='What is stored in private memory?'
lines=[('situation: '+json.dumps(situation,ensure_ascii=False)) if line==old else line for line in lines]
lines=[line for line in lines if not line.startswith(('Contrato literal','Acciones:','Palabras:','Hechos:'))]
en['messages'][-1]['content']='\n'.join(lines)
cases.append({'id':'redacted-en','payload':en,'origin':'synthetic401 EN redacted control'})
mixed=copy.deepcopy(redacted);body=mixed['messages'][-1]['content'];old=fact_line(mixed)
situation=json.loads(old.removeprefix('situation: '));situation['seen'].update(shown=2,total=2,records=[{'label':'favorite color','value':'turquesa'},{'label':'secret','value':'[REDACTED]'}])
mixed['messages'][-1]['content']=body.replace(old,'situation: '+json.dumps(situation,ensure_ascii=False))
cases.append({'id':'mixed-es','payload':mixed,'origin':'synthetic401 mixed visible/protected control'})
out=base/'astra-memory-redaction443';private=local/'C03-memory-redaction443-private'
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
 'method':'Ten paired first-native completions: eight401 retain-value payloads plus EN redacted and mixed ES controls. Only records with value exactly[REDACTED] become redacted:true with value omitted. All other data/payloads, system, request, language, contract, model and sampler unchanged. No private value is available, no tools/effects/source edits. Native projection diagnostic, not guarded composer or product.',
 'new_evidence':'401 source records mark protected values with a string sentinel. Native first answer copies that sentinel and incorrectly denies access; subsequent guarded attempts exhaust. MemoryOperationResponseProjection already owns the sensitivity boundary. Compare typed visibility of that same protected data, never pass the underlying private value or force a visible replacement.',
 'criteria':'All3 protected/mixed cases must explain protected data, preserve visible mixed value, and not deny the verified access or invent another value. Seven unchanged controls must have byte-identical payloads; existing ES name attribution failures remain failures outside this hypothesis, never counted green. No source unless all targeted cases improve, then require boundary tests and guarded/native product verification.',
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
        for variant in ['baseline','typed-redaction']:
            payload=copy.deepcopy(case['payload'])
            if variant=='typed-redaction':
                old=fact_line(payload);situation=json.loads(old.removeprefix('situation: '));changed=False
                for record in situation.get('seen',{}).get('records',[]):
                    if record.get('value')=='[REDACTED]':
                        record.pop('value');record['redacted']=True;changed=True
                if changed:payload['messages'][-1]['content']=payload['messages'][-1]['content'].replace(old,'situation: '+json.dumps(situation,ensure_ascii=False))
                else:assert payload==case['payload']
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
