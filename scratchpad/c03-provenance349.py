"""Test preserved explicit-user provenance after the native348 isolation."""
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

out=root/'artifacts/comprobaciones/C03/astra-provenance349'
out.mkdir(exist_ok=False)
base=Path(os.environ['LOCALAPPDATA'])/'BAXY'
private=base/'C03-provenance349-private'
private.mkdir(exist_ok=False)
prior=json.loads((root/'artifacts/comprobaciones/C03/astra-speaker-primary348/PREREG.json').read_text(encoding='utf-8'))
cases=prior['cases']
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(manifest.read_text(encoding='utf-8-sig'))
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
prereg={'utc':datetime.now(timezone.utc).isoformat(),'cases':cases,'method':'Same eight speaker controls348, baseline native fact payload versus exactly one additional fact in seen: source=facts explicitly saved by the user. Source hypothesis is valid for this private projection because TryProjectRecord accepts only origin=explicit, but currently drops that provenance. No claim that every record is about the user; sister must remain third-party and BAXY retains its own identity. No user declaration/history injected, no prompt/model/sampler/source edit, no effects or promotion. Native first completion only; not a product or fresh-acceptance result.','new_evidence':'346/347 representation changes failed;348 native dialogue preserves all eight speaker meanings (one English reply in Spanish). This points to lost provenance rather than absence of name value. Record origin validation already exists at MemoryOperationResponseProjection.cs; Carter_v2 LLM_CONTEXT_MEMORY_REPORT.md warns against unqualified user-memory identity entering assistant identity.','criteria':'Eight correct speaker/third-party attributions, language intact, no new unsupported implications. A new source phrase must not be adopted based on one name or by weakening publication guards.','pins':{str(path):sha(path) for path in [manifest,root/'src/Baxy.App/MemoryOperationResponseProjection.cs',root/'src/baxy_mind/llm.py',Path(__file__)]},'private':str(private)}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):os.environ.pop(name)
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
client=LlmRuntime()
try:
    client.start_warmup();assert client.wait_warmup(90)
    (out/'SERVER_COMMAND.json').write_text(json.dumps(client._server_command(),indent=2)+'\n',encoding='utf-8')
    for case in cases:
        for variant in ['baseline','provenance']:
            payload=copy.deepcopy(case['reference'])
            if variant=='provenance':
                message=payload['messages'][-1]
                fact_line=next(line for line in message['content'].splitlines() if line.startswith('situation: '))
                facts=json.loads(fact_line.removeprefix('situation: '))
                facts['seen']['source']='facts explicitly saved by the user'
                message['content']=message['content'].replace(fact_line,'situation: '+json.dumps(facts,ensure_ascii=False),1)
            client.begin_request(40)
            try:response=client._post(payload)
            finally:client.end_request()
            result={'id':case['id'],'variant':variant,'answer':response['choices'][0]['message'].get('content'),'finish_reason':response['choices'][0]['finish_reason']}
            with (private/'posts.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps({**result,'payload':payload,'response':response},ensure_ascii=False)+'\n')
            with (out/'replies.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(result,ensure_ascii=False)+'\n')
            print(json.dumps(result,ensure_ascii=True),flush=True)
finally:
    client.close()
    (out/'EXIT.json').write_text(json.dumps({'manifest_unchanged':sha(manifest)==prereg['pins'][str(manifest)]},indent=2)+'\n',encoding='utf-8')
