"""Same model and messages; compare compact GBNF with JSON Schema serialization."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root/'src'),str(root)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-guard-format';out.mkdir(exist_ok=False)
records=[json.loads(line) for line in (base/'astra-negative-contract/posts.jsonl').read_text(encoding='utf-8').splitlines()]
records=[row for row in records if row['stage']=='shape']
schema={'type':'object','properties':{'request_type':{'type':'string','enum':['stable_conversation','external_read','environment_change','incomplete_effect']},'effect_count':{'type':'string','enum':['zero','one','multiple']}},'required':['request_type','effect_count'],'additionalProperties':False}
register=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json';config=json.loads(register.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
prereg={'cases':[row['case'] for row in records],'baseline':'astra-negative-contract/posts.jsonl, stage shape',
        'method':'Eleven consumed/synthetic diagnostic inputs. Replay exact captured system/user messages, sampling, budget and template. Replace only compact GBNF with original equivalent JSON Schema. No change of prompt wording, operation authority, source, model or runtime registration.',
        'schema':schema,'registrationSha256':hashlib.sha256(register.read_bytes()).hexdigest()}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
client=LlmRuntime();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid());gpu.start();ram.start();started=time.monotonic()
try:
    client.start_warmup();assert client.wait_warmup(90)
    for row in records:
        payload=json.loads(json.dumps(row['payload']));payload.pop('grammar')
        payload['response_format']={'type':'json_schema','json_schema':{'name':'baxy_semantic_effect_guard','strict':True,'schema':schema}}
        client.begin_request(35)
        try:response=client._post(payload)
        finally:client.end_request()
        result={'text':row['case'],'baseline':row['response']['choices'][0]['message']['content'],'answer':response['choices'][0]['message']['content'],'finish_reason':response['choices'][0]['finish_reason']}
        with (out/'posts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'case':row['case'],'payload':payload,'response':response},ensure_ascii=False)+'\n')
        with (out/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(result,ensure_ascii=False)+'\n')
        print(json.dumps(result,ensure_ascii=False),flush=True)
        assert gpu.peak_mib is None or gpu.peak_mib<=4096
finally:
    client.close();gpu.stop();ram.stop()
    result={'elapsedSeconds':round(time.monotonic()-started,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'registrationUnchanged':hashlib.sha256(register.read_bytes()).hexdigest()==prereg['registrationSha256']}
    (out/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
