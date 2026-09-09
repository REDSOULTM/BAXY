"""Same full native selector packets, inherited Qwen3.5-4B, no product promotion."""
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
out = base / 'astra-selector-qwen35-71'
out.mkdir(exist_ok=False)
wire = [json.loads(line) for line in (base / 'astra-files64-wire/wire-29264.jsonl').read_text(encoding='utf-8').splitlines()]
references = [json.loads(line) for line in (base / 'astra-selector-references68/posts.jsonl').read_text(encoding='utf-8').splitlines()]
cases = [(f'file{index}', row['payload'], 'filesystem.read.text') for index, row in enumerate(
    [row for row in wire if row['payload'].get('tool_choice') == 'auto'], 1)]
cases += [(f'ref{row["turn"]}', row['payload'], row['expected']) for row in references if row['variant'] == 'full']
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
with model.open('rb') as stream:
    model_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'],
                  BAXY_MIND_NGL=str(config['ngl']))
prereg = {'method': 'Same four exact file selector packets64 and six full-dialogue technical reference packets68. '
          'Only model changes to inherited Qwen3.5-4B-Q4_K_M, served by same b9980CUDA backend with native template, '
          'q8 KV,3x4096 and ngl99. Preserve complete prompts, dialogue, tools, temperature0, seed0,256 tokens and '
          'enable_thinking=false. No preliminary classifier69/70, no wrapper decisions/retries, actual tools, '
          'UI/audio or human reserve. Compare registered-model results already captured64/68; not acceptance. '
          'Prior Qwen35 conversational probes used different sampling/task and showed factual weaknesses; this '
          'new selector failure is the reason to measure this inherited model on a different role, not to erase them.',
          'model': str(model), 'modelSha256': model_sha, 'modelBytes': model.stat().st_size,
          'sourcesConsulted20260907': ['https://huggingface.co/Qwen/Qwen3.5-4B'],
          'samplingDifferenceFromCard': 'General non-thinking card recommends0.7/top_p0.8/top_k20/min_p0/presence1.5. '
          'This is an isolated deterministic selection comparison with the existing role settings, not an optimized global profile.',
          'cases': [{'id': ident, 'expectedOperation': expected} for ident, _, expected in cases],
          'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    (out / 'llama-command.json').write_text(json.dumps(client._server_command(), indent=2), encoding='utf-8')
    assert gpu.peak_mib is None or gpu.peak_mib <= 4096
    for ident, original, expected in cases:
        payload = copy.deepcopy(original)
        context = json.loads(payload['messages'][-1]['content'])
        client.begin_request(40)
        try:
            response = client._post(payload)
        finally:
            client.end_request()
        with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'id': ident, 'text': context['current_request_to_interpret'],
                'expectedOperation': expected, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
        choice = response['choices'][0]
        message = choice['message']
        print(json.dumps({'id': ident, 'operations': [c['function']['name'] for c in message.get('tool_calls', [])],
            'content': message.get('content'), 'finish_reason': choice['finish_reason']}, ensure_ascii=False), flush=True)
        assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
        'ramPeakMiB': ram.peak_mib,
        'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
