"""One bounded native-thinking diagnostic on the already downloaded standard base."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

OUT = ROOT/'artifacts/comprobaciones/C03/astra-gemma-standard-thinking'
assert not OUT.exists()
OUT.mkdir()
source = ROOT/'artifacts/comprobaciones/C03/astra-gemma-inherited-ready/PREREG.json'
prereg = json.loads(source.read_text(encoding='utf-8'))
model = next(path for path in prereg['hashes'] if path.endswith('gemma-4-E2B-it-Q4_K_M.gguf'))
os.environ.update(BAXY_MIND_LLM_GGUF=model, BAXY_MIND_LLAMA_SERVER='D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe',
                  BAXY_MIND_NGL='99', BAXY_MIND_KV_CACHE_TYPE='q8_0')
prereg.update(kind='native-thinking-direct-diagnostic-not-product-acceptance', variants=['standard_base_thinking'],
               hypothesis='Native reasoning may resolve language/fact omissions present with reasoning disabled. Same nine payloads and sampling as standard_base; only enable native thought and allow up to 1024 total generated tokens. No forced intermediate reasoning cutoff.',
               primarySource='https://huggingface.co/google/gemma-4-E2B-it#2-thinking-mode-configuration',
               parentSha256=hashlib.sha256(source.read_bytes()).hexdigest())
for case in prereg['cases']:
    case['payload'] = copy.deepcopy(case['payload'])
    case['payload']['chat_template_kwargs'] = {'enable_thinking': True}
    case['payload']['max_tokens'] = 1024
(OUT/'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')

class Thinking(LlmRuntime):
    def _server_command(self):
        command = super()._server_command()
        command[command.index('--reasoning')+1] = 'auto'
        command[command.index('--reasoning-budget')+1] = '-1'
        return command + ['--reasoning-format', 'deepseek']

client = Thinking()
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
        row = {'variant': 'standard_base_thinking', 'turnId': case['turnId'], 'request': case['request'],
               'seconds': round(time.monotonic()-tick, 3), 'response': response}
        with (OUT/'replies.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')
        choice = response['choices'][0]
        print(json.dumps({'turnId': row['turnId'], 'seconds': row['seconds'], 'finish': choice['finish_reason'],
                           'hasReasoning': bool(choice['message'].get('reasoning_content'))}), flush=True)
except Exception as exc:
    error = f'{type(exc).__name__}: {exc}'
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic()-started, 2), 'gpuPeakMiB': gpu.peak_mib,
               'ramPeakMiB': ram.peak_mib, 'error': error}
    (OUT/'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
