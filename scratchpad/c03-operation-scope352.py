"""Replay the lost private operation identity without changing source or prose instructions."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import json
import os
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind.llm import LlmRuntime

out=root/'artifacts/comprobaciones/C03/astra-operation-scope352'
out.mkdir(exist_ok=False)
base=Path(os.environ['LOCALAPPDATA'])/'BAXY'
private=base/'C03-operation-scope352-private'
private.mkdir(exist_ok=False)
prior=json.loads((root/'artifacts/comprobaciones/C03/astra-private-roles347/PREREG.json').read_text(encoding='utf-8'))
cases=prior['cases']
source=base/'C03-memory-product351-private'
audits=[json.loads(line) for line in (source/'compose-audit.jsonl').read_text(encoding='utf-8').splitlines()]
wire=[json.loads(line) for line in (source/'http-posts.jsonl').read_text(encoding='utf-8').splitlines()]
failure=next(row for row in audits if row.get('stage')=='first' and json.loads(row.get('situation') or '{}').get('cause')=='memory_disabled')
reference=None
for row in wire:
    if row.get('stage')!='request':continue
    if any(message['role']=='user' and ('\nsituation: '+json.dumps(failure['payload'],ensure_ascii=False)) in message['content'] for message in row['payload']['messages']):
        reference=row['payload'];break
assert reference is not None
cases.append({'id':'save-disabled-greeting-request','situation':json.loads(failure['situation']),'reference':reference})
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(manifest.read_text(encoding='utf-8-sig'))
models=[('registered2507',config['gguf']),('available-qwen35','D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')]
prereg={'utc':datetime.now(timezone.utc).isoformat(),'cases':cases,'models':models,'method':'Nine fixed native controls on both existing models, baseline versus adding exactly the typed operation identity already present in the App situation but omitted by Python. All prompt text, seen values, failure cause, user request, roles, samplers and runtime configuration stay unchanged. No prose rule, interpretation rewrite, model/source promotion, effects or UI. First native completions only.','hypothesis':'351 demonstrates scope loss: memory_disabled gets attributed to greeting, enabled to a view. The operation identity names the actual result/failure and is supplied by the authorized owner. This is separate from the failed provenance/record-speech annotations346–349; no further annotation is repeated.','criteria':'Error limited to saving with memory disabled, greeting still possible; enabled clearly refers to memory; no unsupported system observations or internal-code echo. Preserve save/recall/name/third-party/disable meanings. Further source adoption needs both projection tests and integrated replay.','private':str(private)}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name,path in models:
    for key in list(os.environ):
        if key.startswith('BAXY_MIND_'):os.environ.pop(key)
    os.environ.update(BAXY_MIND_LLM_GGUF=path,BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
    client=LlmRuntime()
    try:
        client.start_warmup();assert client.wait_warmup(90)
        (out/(name+'-command.json')).write_text(json.dumps(client._server_command(),indent=2)+'\n',encoding='utf-8')
        for case in cases:
            for variant in ['baseline','operation-scope']:
                payload=copy.deepcopy(case['reference'])
                if variant=='operation-scope':
                    message=payload['messages'][-1]
                    line=next(line for line in message['content'].splitlines() if line.startswith('situation: '))
                    facts=json.loads(line.removeprefix('situation: '))
                    facts['operation']=case['situation']['operation']
                    message['content']=message['content'].replace(line,'situation: '+json.dumps(facts,ensure_ascii=False),1)
                client.begin_request(40)
                try:response=client._post(payload)
                finally:client.end_request()
                result={'id':case['id'],'model':name,'variant':variant,'answer':response['choices'][0]['message'].get('content'),'finish_reason':response['choices'][0]['finish_reason']}
                with (private/'posts.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps({**result,'payload':payload,'response':response},ensure_ascii=False)+'\n')
                with (out/'replies.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(result,ensure_ascii=False)+'\n')
                print(json.dumps(result,ensure_ascii=True),flush=True)
    finally:client.close()
