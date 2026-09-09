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
out = base / 'astra-progress-sampling95'
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
prereg = {'method': 'Non-thinking role-sampler comparison against exact87 six data-activity packets and original '
    'progress instruction. Same GGUF/backend/flags/max_tokens, no source change. Use official Qwen3.5 general '
    'non-thinking profile temperature0.7/top_p0.8/top_k20/min_p0/presence1.5/repeat1 with seeds0,1,2 fixed '
    'before execution; all18 drafts count, never select only a favourable sample. Baseline87 greedy already '
    'recorded. Judge truthful current interpretation, natural language and no execution/actor inversion. '
    'No functions/publication/UI/audio/reserve or runtime promotion.',
    'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'model': model,
    'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
client = LlmRuntime(); gpu = ProcessTreeGpuSampler(os.getpid()); ram = RamSampler(os.getpid())
gpu.start(); ram.start(); started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for case in cases:
        for variant in (0, 1, 2):
            payload = copy.deepcopy(case['payload'])
            if isinstance(variant, int):
                lines = payload['messages'][-1]['content'].splitlines()
                positions = [i for i, line in enumerate(lines) if line.startswith('situation: ')]
                assert len(positions) == 1
                position = positions[0]
                situation = json.loads(lines[position].removeprefix('situation: '))
                situation['state'] = "understanding the person's request"
                lines[position] = 'situation: ' + json.dumps(situation, ensure_ascii=False)
                payload['messages'][-1]['content'] = '\n'.join(lines)
            payload.update(temperature=0.7, top_p=0.8, top_k=20, min_p=0.0,
                presence_penalty=1.5, repeat_penalty=1.0, seed=variant)
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
