"""Preregistered diagnostic only: identical product payloads, base vs inherited LoRA."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

OUT = ROOT / 'artifacts/comprobaciones/C03/astra-gemma-inherited-ready'
MODEL_ROOT = Path('D:/BAXYRuntime/experiments/models/gemma4-e2b-inherited-d3b0fed4')
MODEL = MODEL_ROOT / 'base-gguf/gemma-4-E2B-it-Q4_K_M.gguf'
ADAPTER = MODEL_ROOT / 'adapter-f32.gguf'
SERVER = Path('D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe')
assert not OUT.exists(), 'Never overwrite a preregistered run'
OUT.mkdir()
os.environ.update(BAXY_MIND_LLAMA_SERVER=str(SERVER), BAXY_MIND_LLM_GGUF=str(MODEL),
                  BAXY_MIND_NGL='99', BAXY_MIND_KV_CACHE_TYPE='q8_0')

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

class Captured(Exception):
    pass

class Recorder(LlmRuntime):
    def __init__(self):
        self._gguf = str(MODEL)
        self.payload = None
    def _post(self, payload):
        self.payload = copy.deepcopy(payload)
        raise Captured()

class Candidate(LlmRuntime):
    def __init__(self, adapter):
        super().__init__()
        self.adapter = adapter
    def _server_command(self):
        command = super()._server_command()
        return command + (['--lora', str(ADAPTER)] if self.adapter else [])

prior = ROOT / 'artifacts/comprobaciones/C03/astra-history-ablation-ready/PREREG.json'
cases = [{'turnId': case['turnId'], 'request': case['request'], 'route': 'knowledge',
          'payload': copy.deepcopy(case['full'])}
         for case in json.loads(prior.read_text(encoding='utf-8'))['cases']]
source = ROOT / 'artifacts/comprobaciones/C03/astra-qwen2507-corpus-warm/compose-audit.jsonl'
paired = ROOT / 'artifacts/comprobaciones/C03/astra-qwen2507-corpus-warm/paired.json'
requests = {row['turnId']: row['request'] for row in json.loads(paired.read_text(encoding='utf-8-sig'))}
with source.open(encoding='utf-8-sig') as stream:
    for line in stream:
        row = json.loads(line)
        if row['trace'] not in ['t2', 't4', 't6'] or row['stage'] != 'first':
            continue
        recorder = Recorder()
        try:
            recorder.compose_user_message(requests[row['trace']], row['intent'], {'situation': row['situation']})
        except Captured:
            pass
        assert recorder.payload
        cases.append({'turnId': row['trace'], 'request': requests[row['trace']], 'route': 'status',
                      'payload': recorder.payload, 'verifiedHistoricalSituation': row['situation']})
assert len(cases) == 9
sampling = dict(temperature=.7, top_p=.8, top_k=20, min_p=0, seed=0)
for case in cases:
    case['payload'].update(sampling, cache_prompt=False)
prereg = {'kind': 'direct-model-diagnostic-not-product-acceptance', 'cases': cases,
           'hypothesis': 'The existing historical LoRA improves useful faithful ES/EN/mixed replies over the standard non-QAT Gemma4 E2B base.',
           'scope': 'Six reconstructed knowledge payloads with same history, three reconstructed product compose payloads using verified historical facts. No new PC observation or effects.',
           'acceptance': 'Read every response for correct topic, facts, natural language and requested language. Any material failure blocks promotion; same-model base control isolates adapter effect. Full product acceptance remains separate.',
           'limits': {'gpuMiB': 4096, 'contextPerSlot': 4096, 'ngl': 99, 'kv': 'q8_0'},
           'provenanceLimitation': 'Exact original training base revision was not preserved; verify loader compatibility, do not claim byte-identical historical restoration.',
           'hashes': {str(p): digest(p) for p in [MODEL, ADAPTER, SERVER, ROOT/'src/baxy_mind/llm.py', prior, source]},
           'variants': ['standard_base', 'inherited_lora'], 'sampling': sampling}
(OUT/'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
print('Preregistered 9 cases x 2 variants', flush=True)
results = []
for variant in prereg['variants']:
    client = Candidate(variant == 'inherited_lora')
    gpu = ProcessTreeGpuSampler(os.getpid())
    ram = RamSampler(os.getpid())
    gpu.start(); ram.start()
    started = time.monotonic()
    error = None
    try:
        client.start_warmup()
        ready = False
        for _ in range(120):
            if gpu.peak_mib is not None and gpu.peak_mib > 4096:
                raise RuntimeError('GPU ceiling exceeded during warmup')
            if client.wait_warmup(1):
                ready = True
                break
        if not ready:
            raise RuntimeError('Model failed warmup')
        print(json.dumps({'variant': variant, 'readySeconds': round(time.monotonic()-started, 2)}), flush=True)
        for case in cases:
            if gpu.peak_mib is not None and gpu.peak_mib > 4096:
                raise RuntimeError('GPU ceiling exceeded')
            tick = time.monotonic()
            client.begin_request(30)
            try:
                response = client._post(case['payload'])
            finally:
                client.end_request()
            row = {'variant': variant, 'turnId': case['turnId'], 'request': case['request'],
                   'seconds': round(time.monotonic()-tick, 3), 'response': response}
            with (OUT/'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False)+'\n')
            print(json.dumps({key: row[key] for key in ['variant', 'turnId', 'seconds']}), flush=True)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        print(json.dumps({'variant': variant, 'error': error}), flush=True)
    finally:
        client.close(); gpu.stop(); ram.stop()
        result = {'variant': variant, 'elapsedSeconds': round(time.monotonic()-started, 2),
                  'gpuPeakMiB': gpu.peak_mib, 'ramPeakMiB': ram.peak_mib, 'error': error}
        results.append(result)
        (OUT/'RESULT.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(json.dumps(result), flush=True)
    if error:
        break
