"""Use typed outcome facts as selector history while retaining conversational replies."""
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
out = base / 'astra-selector-facts73'
out.mkdir(exist_ok=False)
wire = [json.loads(line) for line in (base / 'astra-files64-wire/wire-29264.jsonl').read_text(encoding='utf-8').splitlines()]
refs = [json.loads(line) for line in (base / 'astra-selector-references68/posts.jsonl').read_text(encoding='utf-8').splitlines()]
audit = [json.loads(line) for line in (base / 'astra-files64-wire/compose-audit.jsonl').read_text(encoding='utf-8').splitlines()]
failure_row = next(row for row in audit if row.get('trace') == 't1' and row.get('stage') == 'first')
replacements = {failure_row['draft']: json.loads(failure_row['situation'])}
cases = [(f'file{index}', row['payload']) for index, row in enumerate(
    [row for row in wire if row['payload'].get('tool_choice') == 'auto'], 1)]
cases += [(f'ref{row["turn"]}', row['payload']) for row in refs if row['variant'] == 'full']

def search_result(names):
    return {'kind': 'operation', 'operation': 'filesystem.search', 'polarity': 'success',
        'verified': True, 'succeeded': True, 'readOnly': True, 'observed': {'version': 1,
            'entries': [{'resourceId': 'fs_' + str(index) * 32, 'name': name, 'kind': 'file'}
                        for index, name in enumerate(names, 1)], 'count': len(names)}}

reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'],
                  BAXY_MIND_NGL=str(config['ngl']))
prereg = {'method': 'Return to registered Qwen3-2507. Compare exact full selector payloads64/68 with only '
          'earlier assistant machine-result prose replaced by its typed source facts. File cases replace only '
          'the real first absolute-search failure; later out-of-catalog replies are interpretations and are NOT '
          'upgraded into verified observations. Synthetic reference3/4 replace found-files narration by explicit '
          'synthetic typed search fixtures; reference6 uses the assumed failed-search facts. Offers remain literal. '
          'No deletion of stored conversation, rewrite of current requests, extra classifier, prompt or model change. '
          'No actual functions/UI/audio/human reserve; this is a representation comparison before implementation.',
          'syntheticFixtures': {'reft3': search_result(['informe.txt']),
                                'reft4': search_result(['report-a.txt', 'report-b.txt'])},
          'actualFailureSource': replacements,
          'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for ident, original in cases:
        for variant in ('captured', 'typed_result'):
            payload = copy.deepcopy(original)
            context = json.loads(payload['messages'][-1]['content'])
            if variant == 'typed_result':
                for message in context['previous_dialogue_for_references_only']:
                    if message['role'] != 'assistant':
                        continue
                    source = replacements.get(message['content'])
                    if ident in prereg['syntheticFixtures']:
                        source = prereg['syntheticFixtures'][ident]
                    elif ident == 'reft6':
                        source = json.loads(failure_row['situation'])
                    if source is not None:
                        message['content'] = json.dumps(source, ensure_ascii=False)
                payload['messages'][-1]['content'] = json.dumps(context, ensure_ascii=False)
            client.begin_request(40)
            try:
                response = client._post(payload)
            finally:
                client.end_request()
            with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'id': ident, 'variant': variant,
                    'text': context['current_request_to_interpret'], 'payload': payload,
                    'response': response}, ensure_ascii=False) + '\n')
            message = response['choices'][0]['message']
            print(json.dumps({'id': ident, 'variant': variant,
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
