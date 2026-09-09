"""Scope only closed standalone social presentations; native diagnostic, no edits."""
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
from baxy_mind.__main__ import _explicit_social_turn_decision
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler

base=root/'artifacts/comprobaciones/C03'
local=Path(os.environ['LOCALAPPDATA'])/'BAXY'
wire=[]
with (local/'C03-private-product434-private/http-posts.jsonl').open(encoding='utf-8-sig') as f:
    wire=[json.loads(line) for line in f]
reference=next(r['payload'] for r in wire if r.get('stage')=='request'
    and r['payload']['messages'][-1].get('content')=='Me llamo Álvaro.'
    and not r['payload'].get('tools'))
cases=[('actual434-t5','Me llamo Álvaro.',True),
    ('name-en','My name is Nina.',True),('compound-name','Mi nombre es Ana María.',True),
    ('hyphenated-name','My name is Jean-Luc.',True),('gratitude','Muchas gracias.',True),
    ('wellbeing','mi día fue extremadamente duro',True),('farewell','Goodbye Baxy.',True),
    ('name-recall-control','¿Cómo me llamo?',False),
    ('compound-control','Me llamo Ana abre Steam',False),
    ('pending-control','Me llamo Álvaro.',False)]
out=base/'astra-social-context435';private=local/'C03-social-context435-private'
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
 'method':'Ten paired native requests. First baseline is exact captured434T5; others substitute only the last user text, retaining captured system language (Spanish) and history so they are controlled synthetic payloads, not normal product routing. Variant removes prior user/assistant history only for a closed standalone social decision with no pending clarification. Keeps all system messages/current user/settings exactly. Nonclosed recall/compound and explicit pending control are byte-identical. No source edits, prompt change, effects or promotion.',
 'hypothesis':'434T5 routes correctly to social chat but falsely repeats the earlier private save as a new update. A closed greeting/declaration/wellbeing report is self-contained; actual stored dialogue remains intact for referential turns. Inherit chat.starts_new_definition_topic scoping, not global history removal.429 conversation composition without historical save context produced4/4 useful names; this tests history alone before changing renderer or prompts.',
 'criteria':'First baseline reproduces false save; four names/social acts must yield useful acknowledgment without new memory/PC claims. No history removal for pending, compound, or name recall. English substitutions retain Spanish system language deliberately: evaluate semantic/no-effect behavior here, real ES/EN rendering requires later product/runtime verification. No100-human acceptance or UI/physical voice.',
 'cases':[{'id':i,'text':t,'scope_history':s} for i,t,s in cases],
 'model_sha256':sha(model),'backend_sha256':sha(config['llama_server']),'manifest_sha256':sha(manifest),
 'source_sha256':{name:sha(root/name) for name in ['src/baxy_mind/__main__.py','src/baxy_mind/llm.py']},
 'limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'request_seconds':40},'private':str(private)}
assert prereg['model_sha256']=='00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
class Observed(LlmRuntime):
    case='';variant=''
    def _post(self,payload,*args,**kwargs):
        response=super()._post(payload,*args,**kwargs)
        with (private/'posts.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps({'id':self.case,'variant':self.variant,'payload':payload,'response':response},ensure_ascii=False)+'\n')
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
    (out/'command.json').write_text(json.dumps(client._server_command(),indent=2)+'\n',newline='\n')
    for identifier,text,expected_scope in cases:
        original=copy.deepcopy(reference);original['messages'][-1]['content']=text
        if identifier=='actual434-t5':assert original==reference
        scoped=_explicit_social_turn_decision(text,reference['messages'],pending_clarification=identifier=='pending-control')
        use_scope=scoped is not None and scoped.get('conversation_kind')=='social'
        assert use_scope==expected_scope,(identifier,use_scope)
        for variant in ['baseline','closed-social-context']:
            payload=copy.deepcopy(original)
            if variant!='baseline' and use_scope:
                payload['messages']=[m for m in payload['messages'][:-1] if m['role']=='system']+[payload['messages'][-1]]
            if variant=='baseline' or not use_scope:assert payload==original
            client.case=identifier;client.variant=variant;before=time.monotonic();client.begin_request(40)
            try:
                response=client._post(payload);choice=response['choices'][0]
                row={'id':identifier,'text':text,'variant':variant,'history_scoped':variant!='baseline' and use_scope,
                    'answer':choice['message'].get('content'),'finish_reason':choice.get('finish_reason')}
            except Exception as error:row={'id':identifier,'variant':variant,'error':type(error).__name__+':'+str(error)}
            finally:client.end_request()
            row['seconds']=round(time.monotonic()-before,3)
            with (out/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps(row,ensure_ascii=True),flush=True)
            if violations:break
        if violations:break
    complete=not violations
finally:
    stop.set();client.close();guard.join(timeout=5);gpu.stop();ram.stop()
    result={'completed':complete,'violations':violations,'gpu_peak_mib':gpu.peak_mib,'ram_peak_mib':ram.peak_mib,
        'seconds':round(time.monotonic()-started,3),'manifest_unchanged':sha(manifest)==prereg['manifest_sha256']}
    (out/'resources.json').write_text(json.dumps(result,indent=2)+'\n',newline='\n')
assert complete and result['manifest_unchanged']
