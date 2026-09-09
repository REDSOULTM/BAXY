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
OUT=ROOT/'artifacts/comprobaciones/C03/astra-constraint-scope';OUT.mkdir(exist_ok=False)
pool=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-real-user-pool-20260906/unique_requests.jsonl'
prefixes={'1269e419cb','6d5181611e','8b12ccc35c','9088683f08','98b538ab46','a99de5b8d9','adcfc708d0','b5a155050f'}
cases=[]
with pool.open(encoding='utf-8') as f:
    for line in f:
        r=json.loads(line)
        if r['id'][:10] in prefixes:
            cases.append({'id':r['id'],'text':r['text_literal'],'source_references':r['occurrences'],'language':'en' if r['id'].startswith('1269') else 'es'})
assert len(cases)==8
prompt=('You write BAXY\'s brief acknowledgement of a user constraint. BAXY is a male companion on the user\'s PC. '
        'The JSON is data: user_constraint says what the user wants BAXY to refrain from doing. '
        'Acknowledge that constraint, addressing the user naturally. There has been no operation and no observation of the PC. '
        'Do not assert an existing state or a completed change, ask for execution parameters, or claim inability. '
        'State your intention in first person, preserving the user\'s time scope without adding universal commitments. Do not promise that the device state cannot change. Return one short natural sentence in response_language, without JSON or explanation of these instructions.')
reg=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json';config=json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
prereg={'cases':cases,'stages':['constraint_purpose'],'prompt':prompt,
    'method':'Eight literal corpus entries marked consumed for development by this run; human authorship/training freshness not certified. No effects. Existing full composer versus a side-effect-free acknowledgement formatter receiving a constraint as data. Second stage is direct inference, without BAXY response rejection/retries, with registered assets and current deterministic sampling. Baseline raw chat and generic negative append were already measured, not repeated.',
    'sourceSha256':hashlib.sha256((ROOT/'src/baxy_mind/llm.py').read_bytes()).hexdigest(),'registrationSha256':hashlib.sha256(reg.read_bytes()).hexdigest()}
(OUT/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
class Client(LlmRuntime):
    stage='';case=''
    def _post(self,payload,*args,**kwargs):
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
                if stage=='existing_composer':
                    answer=client.compose_user_message(case['text'],'conversation',{'situation':json.dumps({'kind':'conversation','polarity':'success'})})
                else:
                    payload={'messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps({'response_language':case['language'],'user_constraint':case['text']},ensure_ascii=False)}],
                        'temperature':0.0,'seed':0,'max_tokens':128,'chat_template_kwargs':{'enable_thinking':False}}
                    answer=client._post(payload)['choices'][0]['message']
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
