"""Native transport-only comparison inherited from account roles304."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind.llm import LlmRuntime

out=root/'artifacts/comprobaciones/C03/astra-private-roles347'
out.mkdir(exist_ok=False)
base=Path(os.environ['LOCALAPPDATA'])/'BAXY'
private=base/'C03-private-roles347-private'
private.mkdir(exist_ok=False)
prior=json.loads((root/'artifacts/comprobaciones/C03/astra-private-result346/PREREG.json').read_text(encoding='utf-8'))
posts=[json.loads(line) for line in (base/'C03-private-result346-private/posts.jsonl').read_text(encoding='utf-8').splitlines()]
cases=prior['cases']
for case in cases:
    case['reference']=next(row['payload'] for row in posts if row['case']==case['id'] and row['variant']=='baseline')
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(manifest.read_text(encoding='utf-8-sig'))
def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
prereg={'utc':datetime.now(timezone.utc).isoformat(),'cases':cases,'method':'Same eight development controls346. Compare exact first baseline payload with only message-role representation changed: literal user request and unchanged turn instructions stay user; the same situation line becomes a tool result for the actual observed private operation, paired with a preceding assistant tool call. No tools made available, no execution, no source/model/sampling/guard change. First native completion only; not guarded publication, product, UI, voice or acceptance.','inheritance':'c03-account-roles304.py already tested this native tool-return format on four account-read controls; preserved ES attribution, exposed an English path escaping defect. New data: actual345 memory results remain semantically wrong with a literal user request;346 operation-envelope-only did not repair them. Reuse existing exact2507/template documentation and INVES­TIGACION_FORMATO_Y_CLASIFICACION_C03.md; do not retry the rejected shape-only representation.','criteria':'Same names and enable/save/disable facts; no assistant-name contamination, invented system audit, internal fields or unrelated implications. Read all controls individually.','pins':{str(path):sha(path) for path in [manifest,root/'src/baxy_mind/llm.py',Path(__file__)]},'private':str(private)}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'): os.environ.pop(name)
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
client=LlmRuntime()
try:
    client.start_warmup();assert client.wait_warmup(90)
    (out/'SERVER_COMMAND.json').write_text(json.dumps(client._server_command(),indent=2)+'\n',encoding='utf-8')
    for case in cases:
        for variant in ['baseline','tool-return']:
            payload=copy.deepcopy(case['reference'])
            if variant=='tool-return':
                body=payload['messages'][-1]['content']
                fact_line=next(line for line in body.splitlines() if line.startswith('situation: '))
                user='\n'.join(line for line in body.splitlines() if line!=fact_line)
                operation=case['situation']['operation']
                payload['messages']=[*payload['messages'][:-1],{'role':'user','content':user},
                    {'role':'assistant','content':None,'tool_calls':[{'id':'observed_private','type':'function','function':{'name':operation,'arguments':'{}'}}]},
                    {'role':'tool','tool_call_id':'observed_private','name':operation,'content':fact_line}]
            client.begin_request(40)
            try: response=client._post(payload)
            finally: client.end_request()
            answer=response['choices'][0]['message'].get('content')
            result={'id':case['id'],'variant':variant,'answer':answer,'finish_reason':response['choices'][0]['finish_reason']}
            with (private/'posts.jsonl').open('a',encoding='utf-8') as stream: stream.write(json.dumps({**result,'payload':payload,'response':response},ensure_ascii=False)+'\n')
            with (out/'replies.jsonl').open('a',encoding='utf-8') as stream: stream.write(json.dumps(result,ensure_ascii=False)+'\n')
            print(json.dumps(result,ensure_ascii=True),flush=True)
finally:
    client.close()
    (out/'EXIT.json').write_text(json.dumps({'manifest_unchanged':sha(manifest)==prereg['pins'][str(manifest)]},indent=2)+'\n',encoding='utf-8')
