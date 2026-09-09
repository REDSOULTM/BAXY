"""Compare native dialogue roles on currentQwen3.5 failures; no source mutation."""
from pathlib import Path
from datetime import datetime, timezone
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

base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = root / 'artifacts/comprobaciones/C03/astra-native-context361'
private = base / 'C03-native-context361-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
prior = json.loads((root / 'artifacts/comprobaciones/C03/astra-context-selector358/PREREG.json').read_text(encoding='utf-8'))
cases = [{'id': case['id'], 'reference': case['payloads']['bounded-history'], 'expected': case['expected']} for case in prior['cases']]
wire_path = base / 'C03-memory-product360-private/http-posts.jsonl'
wire = [json.loads(line) for line in wire_path.open(encoding='utf-8')]
for number, name in [(13, 'actual360-first-divergence'), (29, 'actual360-both-primary'), (31, 'actual360-both-second-probe')]:
    cases.append({'id': name, 'reference': next(row['payload'] for row in wire if row.get('stage') == 'request' and row['id'] == number), 'expected': []})
for case in cases:
    embedded = json.loads(case['reference']['messages'][-1]['content'])
    alternate = copy.deepcopy(case['reference'])
    alternate['messages'] = [alternate['messages'][0], *embedded['previous_dialogue_for_references_only'],
                             {'role': 'user', 'content': embedded['current_request_to_interpret']}]
    assert all(row['role'] in {'user', 'assistant'} for row in alternate['messages'][1:])
    case['native'] = alternate

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
assert sha(model) == '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
manifest_hash = sha(manifest)
prereg = {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Eleven fixed native selector payloads: eight358 with bounded full history and exact360 HTTP13/29/31. Compare JSON reference envelope against the same dialogue and current request in native user/assistant roles. Identical system text,tools,sampling,template,history content and request. No source or manifest changes,no effects,UI,voice or fresh acceptance.',
    'reason': '359 improves the isolated who-am-I selector but product360 regresses6/7to3/7. Its first divergence36013 proposes file-writing for Yo soy el after reading old save-name requests in the JSON envelope. A later primary36029 correctly abstains, but the separate catalogue probe36031 reverses it to system.identity. First correct the measured first divergence; do not change identity descriptors to treat an unrelated file proposal.',
    'inheritance': '316 tested this shape on2507 with only a greeting and failed;317 left current text literal but retained quoted history and did not improve2507. Do not count those as support. New discriminating input360 and different exact modelQwen3.5 justify this single reevaluation.350 shows the current model binds personal identity in native dialogue; official Qwen function-calling/template77 research supplies the structural option. Reuse docs, no prompt sweep or threshold changes. If this equivalent comparison fails, change strategy, not another prose variant.',
    'criteria': 'Selection of exactly requested operations and no stale prior effects; retain all358 controls including still-failing both-identities. Read every native reply, but do not label selector prose as downstream answer quality. Candidate needs source-owner/privacy tests and complete product replay before adoption.',
    'cases': cases,
    'pins': {str(path): sha(path) for path in [manifest, model, Path(config['llama_server']), wire_path, Path(__file__), root / 'src/baxy_mind/llm.py']},
    'private': str(private),
}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start()
ram.start()
started = time.monotonic()
try:
    client.start_warmup()
    assert client.wait_warmup(90)
    (out / 'SERVER_COMMAND.json').write_text(json.dumps(client._server_command(), indent=2) + '\n', encoding='utf-8')
    for case in cases:
        for variant in ['reference', 'native']:
            payload = copy.deepcopy(case[variant])
            client.begin_request(40)
            try:
                response = client._post(payload)
            finally:
                client.end_request()
            choice = response['choices'][0]
            message = choice['message']
            operations = [call['function']['name'] for call in message.get('tool_calls', [])]
            result = {'id': case['id'], 'variant': variant, 'operations': operations, 'text': message.get('content'), 'finish': choice['finish_reason'], 'matches_expected': operations == case['expected']}
            with (private / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({**result, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
            with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(result, ensure_ascii=False) + '\n')
            print(json.dumps(result, ensure_ascii=True), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close()
    gpu.stop()
    ram.stop()
    (out / 'RESOURCES.json').write_text(json.dumps({'gpuPeakMiB': gpu.peak_mib, 'ramPeakMiB': ram.peak_mib, 'seconds': round(time.monotonic() - started, 2)}, indent=2) + '\n', encoding='utf-8')
assert sha(manifest) == manifest_hash
(out / 'EXIT.json').write_text(json.dumps({'manifest_unchanged': True}) + '\n', encoding='utf-8')
