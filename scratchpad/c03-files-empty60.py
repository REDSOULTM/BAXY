"""One native cause ablation; no product source change."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / 'src'), str(root)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-files-empty60'
out.mkdir(exist_ok=False)
rows = [json.loads(line) for line in (base / 'astra-files-scope59/posts.jsonl').read_text(encoding='utf-8').splitlines()]
rows = [row for row in rows if row['variant'] == 'scope']
assert len(rows) == 2
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'],
                  BAXY_MIND_NGL=str(config['ngl']))
prereg = {'method': 'Reuse the two scope59 native HTTP payloads byte-for-byte except one cause value: '
          'step data missing becomes no matches in the searched scope. The captured verified lookup has count=0; '
          'a successful empty search is not evidence of unavailable system data. Preserve scope=sandbox, original requests, '
          'all other facts, BAXY prompts and sampling. Native generation without validators/retries; not raw model only. '
          'No product source promotion, PC effects, UI/audio or human reserve. Scope59 alone gave 0/2 useful replies.',
          'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest(),
          'sourcePostsSha256': hashlib.sha256((base / 'astra-files-scope59/posts.jsonl').read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, indent=2), encoding='utf-8')
client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for row in rows:
        payload = copy.deepcopy(row['payload'])
        user = next(message for message in payload['messages'] if message['role'] == 'user')
        assert user['content'].count('step data missing') == 1
        user['content'] = user['content'].replace('step data missing', 'no matches in the searched scope', 1)
        client.begin_request(40)
        try:
            response = client._post(payload)
        finally:
            client.end_request()
        with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'turn': row['turn'], 'text': row['text'], 'payload': payload,
                                     'response': response}, ensure_ascii=False) + '\n')
        choice = response['choices'][0]
        print(json.dumps({'turn': row['turn'], 'raw': choice['message'].get('content'),
                          'finish_reason': choice.get('finish_reason')}, ensure_ascii=False), flush=True)
        assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
              'ramPeakMiB': ram.peak_mib,
              'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
