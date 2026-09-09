"""Base vs pilot LoRA on the frozen 42 holdout and 9 historical development cases."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler

OUT=ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot4-evaluation'
assert not OUT.exists()
BASE=Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f')
ADAPTER=BASE/'c03-pilot-lora-v4-f32.gguf'
PREVIOUS=BASE/'c03-pilot-lora-v3-f32.gguf'
MODEL=Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf')
assert ADAPTER.is_file()
training=json.loads((ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot4-training/RESULT.json').read_text())
assert training['status']=='trained-not-promoted' and training['gpuPeakMiB']<=4096
def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
holdout=ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot4-data/HOLDOUT.jsonl'
prior=ROOT/'artifacts/comprobaciones/C03/astra-gemma-inherited-ready/PREREG.json'
cases=[dict(row,group='heldout') for row in map(json.loads,holdout.read_text(encoding='utf-8').splitlines())]
cases += [dict(case,id='previous-'+case['turnId'],group='previous-development') for case in json.loads(prior.read_text(encoding='utf-8'))['cases']]
assert len(cases)==51
for case in cases:
    case['payload'].update(temperature=.7,top_p=.8,top_k=20,min_p=0,seed=0,cache_prompt=False)
OUT.mkdir()
prereg={'kind':'direct-model-pilot-evaluation-not-product-acceptance','cases':cases,'variants':['pilot3','pilot4'],
         'limits':{'gpuMiB':4096,'timeoutSeconds':30,'contextPerSlot':4096},
         'criterion':'Read each response against exact requested language, facts and usefulness. Improvement must generalize to the frozen heldout topics/states and preserve ES/EN. Does not certify all product routes.',
         'hashes':{str(path):digest(path) for path in [MODEL,PREVIOUS,ADAPTER,holdout,prior,ROOT/'src/baxy_mind/llm.py']},
         'trainingAdapterSha256':training['adapterSha256']}
(OUT/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
os.environ.update(BAXY_MIND_LLM_GGUF=str(MODEL),BAXY_MIND_LLAMA_SERVER='D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe',BAXY_MIND_NGL='99',BAXY_MIND_KV_CACHE_TYPE='q8_0')
class Candidate(LlmRuntime):
    def __init__(self,adapter):
        super().__init__();self.adapter=adapter
    def _server_command(self):
        return super()._server_command()+['--lora',str(ADAPTER if self.adapter else PREVIOUS)]
results=[]
for variant in ['pilot3','pilot4']:
    client=Candidate(variant=='pilot4');gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid())
    gpu.start();ram.start();started=time.monotonic();error=None
    try:
        client.start_warmup();assert client.wait_warmup(60)
        for case in cases:
            if gpu.peak_mib is not None and gpu.peak_mib>4096:raise RuntimeError('GPU ceiling exceeded')
            tick=time.monotonic();client.begin_request(30)
            try:response=client._post(case['payload'])
            finally:client.end_request()
            row={'variant':variant,'id':case['id'],'group':case['group'],'request':case['request'],
                 'seconds':round(time.monotonic()-tick,3),'response':response}
            with (OUT/'replies.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps({'variant':variant,'id':case['id'],'seconds':row['seconds']}),flush=True)
    except Exception as exc:error=f'{type(exc).__name__}: {exc}'
    finally:
        client.close();gpu.stop();ram.stop()
        result={'variant':variant,'elapsedSeconds':round(time.monotonic()-started,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'error':error}
        results.append(result);(OUT/'RESULT.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
    if error:break
