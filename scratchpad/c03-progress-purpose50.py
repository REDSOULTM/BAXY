"""Capture the real early composer payload, then change only message purpose."""
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
out = base / 'astra-progress-purpose50'
out.mkdir(exist_ok=False)
rows = json.loads((base / 'astra-clock49/paired.json').read_text(encoding='utf-8'))
texts = [rows[index]['request'] for index in (0, 1, 2, 3, 5)]
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
prereg = {
    'texts': texts,
    'method': 'Five consumed readonly requests. Call the exact early-turn compose API with status/acting/success and no context, recording every native payload and response before validation. Then replay each captured first payload directly to the same native server, changing only situation.kind from status to progress. No guards or retries on this latter comparison. Same actual system messages, user text, sampler, template, token budget. No source/model promotion, no human reserve, no UI/voice claim. A native variant passes only if it reports ongoing work without invented observations or unavailable-clock claims.',
    'sourceSha256': hashlib.sha256((root / 'src/baxy_mind/llm.py').read_bytes()).hexdigest(),
    'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest(),
}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')

class Client(LlmRuntime):
    stage = 'product'
    text = ''
    first_payloads = {}

    def _post(self, payload, *args, **kwargs):
        captured = copy.deepcopy(payload)
        response = super()._post(payload, *args, **kwargs)
        if self.stage == 'product':
            self.first_payloads.setdefault(self.text, captured)
        with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'stage': self.stage, 'text': self.text,
                                     'payload': captured, 'response': response}, ensure_ascii=False) + '\n')
        choice = response['choices'][0]
        print(json.dumps({'stage': self.stage, 'text': self.text,
                          'raw': choice['message'].get('content'),
                          'finish_reason': choice.get('finish_reason')}, ensure_ascii=False), flush=True)
        return response

client = Client()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
started = time.monotonic()
published = []
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for text in texts:
        client.text = text
        client.begin_request(40)
        try:
            answer = client.compose_user_message(text, 'status', {
                'situation': json.dumps({'kind': 'status', 'cause': 'acting', 'polarity': 'success'})
            })
            published.append({'text': text, 'answer': answer})
        except Exception as exc:
            published.append({'text': text, 'error': type(exc).__name__ + ': ' + str(exc)})
        finally:
            client.end_request()
    (out / 'published.json').write_text(json.dumps(published, ensure_ascii=False, indent=2), encoding='utf-8')
    client.stage = 'native_progress_kind'
    for text in texts:
        client.text = text
        payload = copy.deepcopy(client.first_payloads[text])
        content = payload['messages'][-1]['content']
        assert content.count('"kind": "status"') == 1
        payload['messages'][-1]['content'] = content.replace('"kind": "status"', '"kind": "progress"', 1)
        client.begin_request(40)
        try:
            client._post(payload)
        finally:
            client.end_request()
        assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2),
              'gpuPeakMiB': gpu.peak_mib, 'ramPeakMiB': ram.peak_mib,
              'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
