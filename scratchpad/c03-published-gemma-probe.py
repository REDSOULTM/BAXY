"""Measure the historical published GGUF on the frozen nine-case comparison."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

OUT = ROOT/'artifacts/comprobaciones/C03/astra-gemma-published'
assert not OUT.exists()
model_root = Path('D:/BAXYRuntime/experiments/models/baxy-gemma4-e2b-published-f9b84ecd')
verified = json.loads((model_root/'VERIFIED.json').read_text(encoding='utf-8'))
model = Path(verified['path'])
with model.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == verified['sha256']
OUT.mkdir()
source = ROOT/'artifacts/comprobaciones/C03/astra-gemma-inherited-ready/PREREG.json'
prereg = json.loads(source.read_text(encoding='utf-8'))
prereg.update(kind='published-historical-model-direct-diagnostic-not-product-acceptance',
               variants=['published_baxy'], hypothesis='Evaluate the actual published BAXY GGUF rather than a reconstruction with uncertain training-base revision. Same nine prompts and sampler as the standard-base control.',
               model=str(model), modelSha256=verified['sha256'],
               modelRevision='f9b84ecdcd4ffdc112a5baa21b86d553a9360c71',
               parentSha256=hashlib.sha256(source.read_bytes()).hexdigest(),
               provenanceLimitation='The published author artifact is verified byte-for-byte; no claim that it matches the local adapter or a past successful C03 acceptance run.')
prereg['hashes'] = {k:v for k,v in prereg['hashes'].items() if not k.endswith('.gguf')}
prereg['hashes'][str(model)] = verified['sha256']
(OUT/'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER='D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe',
                  BAXY_MIND_NGL='99', BAXY_MIND_KV_CACHE_TYPE='q8_0')
client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid()); ram = RamSampler(os.getpid())
gpu.start(); ram.start(); started = time.monotonic(); error = None
try:
    client.start_warmup()
    assert client.wait_warmup(60), 'Warmup failed'
    for case in prereg['cases']:
        if gpu.peak_mib is not None and gpu.peak_mib > 4096:
            raise RuntimeError('GPU ceiling exceeded')
        tick = time.monotonic()
        client.begin_request(30)
        try:
            response = client._post(case['payload'])
        finally:
            client.end_request()
        row = {'variant': 'published_baxy', 'turnId': case['turnId'], 'request': case['request'],
               'seconds': round(time.monotonic()-tick, 3), 'response': response}
        with (OUT/'replies.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')
        print(json.dumps({key: row[key] for key in ['turnId', 'seconds']}), flush=True)
except Exception as exc:
    error = f'{type(exc).__name__}: {exc}'
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic()-started, 2), 'gpuPeakMiB': gpu.peak_mib,
               'ramPeakMiB': ram.peak_mib, 'error': error}
    (OUT/'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
