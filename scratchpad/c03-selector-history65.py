"""Replay exact native selector packets with isolated history/authority changes."""
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
out = base / 'astra-selector-history65'
out.mkdir(exist_ok=True)
assert all(not (out / name).exists() for name in ('PREREG.json', 'posts.jsonl', 'RESULT.json'))
wire_path = base / 'astra-files64-wire/wire-29264.jsonl'
packets = [json.loads(line) for line in wire_path.read_text(encoding='utf-8').splitlines()]
selected = [row for row in packets if row['payload'].get('tool_choice') == 'auto']
assert len(selected) == 4, len(selected)
extra = (' Previous dialogue is only for resolving references. Earlier failures apply to their '
         'exact requests and do not remove declared capabilities for a new request.')
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'],
                  BAXY_MIND_NGL=str(config['ngl']))
prereg = {'method': 'Four exact source63 native selector payloads recorded in files64-wire; clock uses its existing deterministic route. '
          'Compare captured with only previous_dialogue_for_references_only cleared, and with full captured '
          'history plus one instruction about past failure scope and declared capability authority. '
          'Tools, request, template, seed, sampler, token limit unchanged; no BAXY decision guards or retries. '
          'No actual function execution, UI/audio or fresh human acceptance. This is not wrapper-free LLM.',
          'wireSha256': hashlib.sha256(wire_path.read_bytes()).hexdigest(), 'addedInstruction': extra,
          'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for index, packet in enumerate(selected, 1):
        for variant in ('captured', 'no_context', 'scoped_history'):
            payload = copy.deepcopy(packet['payload'])
            context = json.loads(payload['messages'][-1]['content'])
            if variant == 'no_context':
                context['previous_dialogue_for_references_only'] = []
                payload['messages'][-1]['content'] = json.dumps(context, ensure_ascii=False)
            elif variant == 'scoped_history':
                payload['messages'][0]['content'] += extra
            client.begin_request(40)
            try:
                response = client._post(payload)
            finally:
                client.end_request()
            with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'turn': f't{index}', 'text': context['current_request_to_interpret'],
                    'variant': variant, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
            message = response['choices'][0]['message']
            print(json.dumps({'turn': index, 'variant': variant,
                'operations': [c['function']['name'] for c in message.get('tool_calls', [])],
                'content': message.get('content'), 'finish': response['choices'][0]['finish_reason']}, ensure_ascii=False), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
        'ramPeakMiB': ram.peak_mib,
        'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
