"""Reassess the available model on the new native attribution failures, without promotion."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import sys
import time

root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'src'),str(root)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler

out=root/'artifacts/comprobaciones/C03/astra-model-memory350'
out.mkdir(exist_ok=False)
base=Path(os.environ['LOCALAPPDATA'])/'BAXY'
private=base/'C03-model-memory350-private'
private.mkdir(exist_ok=False)
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(manifest.read_text(encoding='utf-8-sig'))
prior=json.loads((root/'artifacts/comprobaciones/C03/astra-provenance349/PREREG.json').read_text(encoding='utf-8'))
cases=[{'id':case['id'],'payload':case['reference']} for case in prior['cases']]
other=json.loads((root/'artifacts/comprobaciones/C03/astra-private-roles347/PREREG.json').read_text(encoding='utf-8'))
cases.extend({'id':case['id'],'payload':case['reference']} for case in other['cases'] if case['situation']['operation']!='memory.recall')
wire=[json.loads(line) for line in (base/'C03-memory-product345-private/http-posts.jsonl').read_text(encoding='utf-8').splitlines()]
for number,identifier in [(21,'actual-chat-who'),(27,'actual-chat-both')]:
    cases.append({'id':identifier,'payload':next(row['payload'] for row in wire if row.get('stage')=='request' and row['id']==number)})
models=[('registered2507',Path(config['gguf'])),('available-qwen35',Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf'))]
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
hashes={name:sha(path) for name,path in models}
assert hashes['available-qwen35']=='00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
manifest_hash=sha(manifest)
prereg={'utc':datetime.now(timezone.utc).isoformat(),'method':'Thirteen fixed development payloads: eight speaker controls348, enable/save/disable346 and exact actual conversation requests21/27 from product345 including their original history. Compare registered2507 with already available Qwen3.5-4B-Q4_K_M, sequentially under the same b9980 context/KV/sampling and unchanged payloads. Existing _post system-prefix normalization77 retained for both. Native first responses only, not product publication, effects, UI, voice or fresh acceptance. Runtime manifest is not changed.','reason':'Three result/provenance variants346/347/349 fail the same Spanish speaker attribution and self-name controls.348 shows the same model can bind explicit human dialogue; the actual full chat21 still denies personal knowledge. Stop appending metadata or phrase guards. New discriminating failures justify revisiting the available candidate before another architecture/prompt change.','inheritance':'INVESTIGACION_MODELO_C03.md Qwen3.5/75–77 and INVES­TIGACION_FORMATO_Y_CLASIFICACION_C03.md: exact template/current backend already researched. Native template normalization77 is adopted. Files77 initially7/10, role repair78 then9/10; no historic full promotion. This test does not erase those constraints or claim a model-wide improvement.','criteria':'Correct speaker and third-party attribution, no fabricated system inspection or global sensitive-data absence, direct contextual identity answers. Preserve ES/EN and assess all results individually. Any further candidate adoption also needs broader routes/guards/product and joint resources.','cases':cases,'models':[{'name':name,'path':str(path),'sha256':hashes[name]} for name,path in models],'manifest_sha256':manifest_hash,'llama_sha256':sha(Path(config['llama_server'])),'source_sha256':sha(root/'src/baxy_mind/llm.py'),'private':str(private)}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name,path in models:
    for key in list(os.environ):
        if key.startswith('BAXY_MIND_'):os.environ.pop(key)
    os.environ.update(BAXY_MIND_LLM_GGUF=str(path),BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
    client=LlmRuntime();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid())
    gpu.start();ram.start();started=time.monotonic()
    try:
        client.start_warmup();assert client.wait_warmup(90)
        (out/(name+'-command.json')).write_text(json.dumps(client._server_command(),indent=2)+'\n',encoding='utf-8')
        for case in cases:
            client.begin_request(40)
            try:response=client._post(copy.deepcopy(case['payload']))
            finally:client.end_request()
            result={'id':case['id'],'model':name,'answer':response['choices'][0]['message'].get('content'),'finish_reason':response['choices'][0]['finish_reason']}
            with (private/'posts.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps({**result,'payload':case['payload'],'response':response},ensure_ascii=False)+'\n')
            with (out/'replies.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(result,ensure_ascii=False)+'\n')
            print(json.dumps(result,ensure_ascii=True),flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib<=4096
    finally:
        client.close();gpu.stop();ram.stop()
        resources={'model':name,'seconds':round(time.monotonic()-started,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib}
        with (out/'resources.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(resources)+'\n')
        print(json.dumps(resources),flush=True)
assert sha(manifest)==manifest_hash
(out/'EXIT.json').write_text(json.dumps({'manifest_unchanged':True})+'\n',encoding='utf-8')
