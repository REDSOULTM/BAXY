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

sys.stdout.reconfigure(encoding='utf-8')
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-progress-phase85'
out.mkdir(exist_ok=False)
source = base / 'astra-progress-baseline82/posts.jsonl'
cases = [json.loads(s) for s in source.read_text(encoding='utf-8').splitlines()]
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
model = 'D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf'
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=model, BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
prereg = {'method': 'Prototype only: exact six first-compose packets82, no source/prompt/model/sampler change. '
    'Compare captured in-progress data with an additional phase=understanding field. This phase exists in the App '
    'while classifying/answering but is currently discarded by milestone facts. The test assumes that known phase '
    'for all six fixtures; do not claim observed publication or that file operations executed. A why question must '
    'not become a new read. No functions/UI/audio/human reserve or source promotion.',
    'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'model': model,
    'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
client = LlmRuntime(); gpu = ProcessTreeGpuSampler(os.getpid()); ram = RamSampler(os.getpid())
gpu.start(); ram.start(); started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for case in cases:
        for variant in ('captured', 'understanding'):
            payload = copy.deepcopy(case['payload'])
            if variant == 'understanding':
                lines = payload['messages'][-1]['content'].splitlines()
                positions = [i for i, line in enumerate(lines) if line.startswith('situation: ')]
                assert len(positions) == 1
                position = positions[0]
                situation = json.loads(lines[position].removeprefix('situation: '))
                situation['phase'] = 'understanding'
                lines[position] = 'situation: ' + json.dumps(situation, ensure_ascii=False)
                payload['messages'][-1]['content'] = '\n'.join(lines)
            client.begin_request(40)
            try:
                response = client._post(payload)
            finally:
                client.end_request()
            row = {'turn': case['turn'], 'text': case['text'], 'variant': variant, 'payload': payload, 'response': response}
            with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(json.dumps({'turn': case['turn'], 'variant': variant, 'choice': response['choices'][0]}, ensure_ascii=False), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
              'ramPeakMiB': ram.peak_mib, 'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
