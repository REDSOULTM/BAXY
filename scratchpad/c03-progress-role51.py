"""Replay exact captured progress payloads, making the narration task explicit."""
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
out = base / 'astra-progress-role51'
out.mkdir(exist_ok=False)
captured = {}
with (base / 'astra-progress-purpose50/posts.jsonl').open(encoding='utf-8') as stream:
    for line in stream:
        row = json.loads(line)
        if row['stage'] == 'product':
            captured.setdefault(row['text'], row['payload'])
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
prereg = {
    'texts': list(captured),
    'method': 'Five direct native completions from exact first payloads captured by progress-purpose50. Append one system instruction specifying the current task as first-person progress narration with no results yet. Preserve original user request and situation unchanged; same model/template/sampler/budget, no guards or retries. This restores the scoped narration responsibility present in historical44b7c45 without prescribing Sigo/Still working or an output template. Two prior data-representation variants failed; this tests task instruction instead. No source promotion, PC effects, human reserve or UI/audio acceptance.',
    'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest(),
}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for text, captured_payload in captured.items():
        payload = copy.deepcopy(captured_payload)
        payload['messages'][0]['content'] += '\n' + 'For this turn, write a brief first-person progress update about working on the request. The requested results are not available yet. Do not answer the request, report measurements or claim completed effects. Do not ask the person to perform the work.'
        client.begin_request(40)
        try:
            response = client._post(payload)
        finally:
            client.end_request()
        with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'text': text, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
        choice = response['choices'][0]
        print(json.dumps({'text': text, 'raw': choice['message'].get('content'),
                          'finish_reason': choice.get('finish_reason')}, ensure_ascii=False), flush=True)
        assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2),
              'gpuPeakMiB': gpu.peak_mib, 'ramPeakMiB': ram.peak_mib,
              'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
