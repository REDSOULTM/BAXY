"""Measure a context-dependence decision before native selection, with literal requests."""
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
out = base / 'astra-selector-context69'
out.mkdir(exist_ok=False)
wire = [json.loads(line) for line in (base / 'astra-files64-wire/wire-29264.jsonl').read_text(encoding='utf-8').splitlines()]
reference = [json.loads(line) for line in (base / 'astra-selector-references68/posts.jsonl').read_text(encoding='utf-8').splitlines()]
cases = [(f'file{index}', row['payload'], False, 'filesystem.read.text') for index, row in enumerate(
    [row for row in wire if row['payload'].get('tool_choice') == 'auto'], 1)]
cases += [(f'ref{row["turn"]}', row['payload'], True, row['expected']) for row in reference if row['variant'] == 'full']
prompt = ('Decide whether interpreting the current message requires earlier conversation. '
          'Return needs_dialogue=true only when earlier utterances are needed to identify what is being requested '
          'or referred to, including acceptance, correction, ellipsis or a reference to prior results. '
          'A fully stated new request does not need earlier dialogue. Needing to inspect computer state or obtain '
          'a tool argument is not itself a need for dialogue. Do not answer the message or select an operation. '
          'Return only the JSON decision.')
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'],
                  BAXY_MIND_NGL=str(config['ngl']))
prereg = {'method': 'Four consumed file requests with captured prior dialogue and six synthetic reference controls68. '
          'One bounded no-tools context-dependence decision sees only the literal current request, then the unchanged '
          'native selector sees either its full original dialogue or none. No rewrite, catalogue change, operation '
          'authorization or visible response. Compare original69 selection to already captured64/68, not another '
          'uncontrolled model. Same registered model/template/sampler. No UI/audio/human reserve or source promotion.',
          'contextPrompt': prompt, 'cases': [{'id': ident, 'needsDialogue': need, 'operation': op}
                                           for ident, _, need, op in cases],
          'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for ident, original, expected_need, expected_op in cases:
        context = json.loads(original['messages'][-1]['content'])
        current = context['current_request_to_interpret']
        dependency = {'messages': [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': current}],
            'temperature': 0.0, 'seed': 0, 'max_tokens': 32, 'chat_template_kwargs': {'enable_thinking': False},
            'response_format': {'type': 'json_schema', 'json_schema': {'name': 'dialogue_dependency', 'strict': True,
                'schema': {'type': 'object', 'properties': {'needs_dialogue': {'type': 'boolean'}},
                    'required': ['needs_dialogue'], 'additionalProperties': False}}}}
        client.begin_request(40)
        try:
            decision_response = client._post(dependency)
            decision = json.loads(decision_response['choices'][0]['message']['content'])
            assert type(decision.get('needs_dialogue')) is bool and len(decision) == 1
            payload = copy.deepcopy(original)
            if not decision['needs_dialogue']:
                context['previous_dialogue_for_references_only'] = []
                payload['messages'][-1]['content'] = json.dumps(context, ensure_ascii=False)
            response = client._post(payload)
        finally:
            client.end_request()
        with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'id': ident, 'text': current, 'expectedNeedsDialogue': expected_need,
                'expectedOperation': expected_op, 'dependencyPayload': dependency, 'dependencyResponse': decision_response,
                'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
        message = response['choices'][0]['message']
        print(json.dumps({'id': ident, 'needsDialogue': decision['needs_dialogue'], 'expectedNeedsDialogue': expected_need,
            'operations': [c['function']['name'] for c in message.get('tool_calls', [])],
            'content': message.get('content')}, ensure_ascii=False), flush=True)
        assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
        'ramPeakMiB': ram.peak_mib,
        'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
