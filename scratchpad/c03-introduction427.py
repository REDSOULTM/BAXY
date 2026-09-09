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
    ('actual426-t5','Me llamo Álvaro.','no_effect'),
    ('name-en','My name is Nina.','no_effect'),
    ('compound-name-es','Me llamo Ana María.','no_effect'),
    ('third-person','My brother is called Omar.','no_effect'),
    ('negative-save','No guardes mi nombre.','no_effect'),
    ('account-en','What is my Windows username?','complete'),
    ('account-es','Dime la cuenta de Windows actual.','complete'),
    ('missing-app-es','Abre una aplicación.','not_complete'),
    ('missing-app-en','Open an app.','not_complete'),
    ('volume','Set the volume to 30.','complete'),
    ('intro-plus-action','Me llamo César. Pon el volumen al 30.','complete'),
    ('explicit-save','My name is Maya. Save my name.','complete'),
    ('explicit-private-read','What name have you saved in private memory?','complete'),
]
out=base/'astra-introduction427';private=local/'C03-introduction427-private'
out.mkdir(exist_ok=False);private.mkdir(exist_ok=False)
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):os.environ.pop(name)
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(manifest.read_text(encoding='utf-8-sig'))
model=Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
os.environ.update(BAXY_MIND_LLM_GGUF=str(model),BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
prereg={'utc':datetime.now(timezone.utc).isoformat(),'method':'Native AUTO request replay: first case is byte-equivalent JSON payload captured426T5 (including welcome/history/catalog/tools); remaining cases change only the last user text, synthetic development. Pair each with the existing LlmRuntime._verify_semantic_effect_shape current-text-only classifier without catalog. No new prompt/decision injected, no source mutation or product effects. This compares two existing roles, not one-variable prompt causality. A cold replay may differ from original scheduling; record reproduction before interpreting. Not model-alone without BAXY prompt, not product or fresh acceptance.',
 'hypothesis':'Catalog AUTO maps a self-introduction to Windows identity. Determine whether existing catalog-free speech-act guard distinguishes the statement from actual account reads, incomplete apps and compound/save requests. Prior source comments around __main__5780 rejected guard over grammar-recognized colloquial actions; do not override explicit recognized intents. Source413/414 early read recovery failed cold/warm; this experiment does not reintroduce it. Source349 provenance did not fix speaker attribution and is unrelated to the first routing error.',
 'criteria':'Actual426 native primary reproduction must be recorded. Guard must say no_effect for five declarative/prohibitory controls, complete for account/volume/explicit-save/private-read, not_complete for missing app. Interpret each case individually. If failures remain, no blanket adoption or extra cascade. Confirm known shape limitations before redesign.',
 'cases':[{'id':i,'text':t,'expected_guard':e} for i,t,e in cases], 'reference_private':str(source/'introduction-pairs.json'),'reference_sha256':sha(source/'introduction-pairs.json'),
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
    for identifier,text,expected in cases:
        payload=copy.deepcopy(reference);payload['messages'][-1]['content']=text
        if identifier=='actual426-t5':assert payload==reference
        row={'id':identifier,'text':text,'expected_guard':expected}
        for role in ['native_auto','existing_guard']:
            client.case=identifier;client.role=role;before=time.monotonic();client.begin_request(40)
            try:
                if role=='native_auto':
                    response=client._post(payload)
                    result=(response.get('choices') or [{}])[0]
                    row['native_message']=result.get('message');row['finish_reason']=result.get('finish_reason')
                else:row['guard']=client._verify_semantic_effect_shape(text)
            except Exception as error:
                row[role+'_error']=type(error).__name__+':'+str(error)
            finally:client.end_request()
            row[role+'_seconds']=round(time.monotonic()-before,3)
        with (out/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps(row,ensure_ascii=True),flush=True)
        if violations:break
    complete=not violations
finally:
    stop.set();client.close();guard.join(timeout=5);gpu.stop();ram.stop()
    result={'completed':complete,'violations':violations,'gpu_peak_mib':gpu.peak_mib,'ram_peak_mib':ram.peak_mib,'seconds':round(time.monotonic()-started,3),'manifest_unchanged':sha(manifest)==prereg['manifest_sha256']}
    (out/'resources.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
assert complete and result['manifest_unchanged']
