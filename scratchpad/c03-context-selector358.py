"""Isolate the second history truncation on the observed personal-identity selector."""
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
from baxy_mind.llm import LlmRuntime, _bounded_history
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = root / 'artifacts/comprobaciones/C03/astra-context-selector358'
private = base / 'C03-context-selector358-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
source = base / 'C03-memory-product355-private'
wire = [json.loads(line) for line in (source / 'http-posts.jsonl').open(encoding='utf-8')]
original = next(row['payload'] for row in wire if row.get('stage') == 'request' and row['id'] == 20)
embedded = json.loads(original['messages'][-1]['content'])
history = []
for row in map(json.loads, (source / 'capture/events.jsonl').open(encoding='utf-8-sig')):
    if row.get('type') != 'event' or row['event'].get('type') != 'activity':
        continue
    entry = row['event']['entry']
    if entry['src'] == 'YOU' and entry['msg'] == embedded['current_request_to_interpret']:
        break
    if entry['src'] in {'YOU', 'BAXY'}:
        history.append({'role': 'user' if entry['src'] == 'YOU' else 'assistant', 'content': entry['msg']})
history = _bounded_history(history)
assert history[-6:] == embedded['previous_dialogue_for_references_only']
assert any(row['role'] == 'user' and 'me llamo emmanuel' in row['content'].casefold() for row in history)
cases = [
    {'id': 'actual-personal-who', 'text': 'quien soy', 'history': history, 'expected': []},
    {'id': 'explicit-windows-with-personal-history', 'text': '¿Cuál es la cuenta de Windows de este proceso?', 'history': history, 'expected': ['baxy_system__identity']},
    {'id': 'fresh-who-inherited-criterion', 'text': 'quien soy', 'history': [], 'expected': ['baxy_system__identity']},
    {'id': 'assistant-identity', 'text': 'quien eres', 'history': history, 'expected': []},
    {'id': 'both-identities', 'text': 'dime quien eres tu y quien soy yo', 'history': history, 'expected': []},
    {'id': 'english-personal', 'text': 'Who am I?', 'history': [
        {'role': 'user', 'content': 'My name is Jordan.'},
        {'role': 'assistant', 'content': 'Hello Jordan.'},
        {'role': 'user', 'content': 'Explain gravity briefly.'},
        {'role': 'assistant', 'content': 'Gravity attracts objects with mass toward one another.'},
        {'role': 'user', 'content': 'And eclipses?'},
        {'role': 'assistant', 'content': 'An eclipse occurs when one celestial body blocks light from reaching another.'},
        {'role': 'user', 'content': 'Thanks.'},
        {'role': 'assistant', 'content': 'You are welcome.'},
    ], 'expected': []},
    {'id': 'third-person-reference', 'text': "What's my sister's name?", 'history': [
        {'role': 'user', 'content': "My sister's name is Olivia."},
        {'role': 'assistant', 'content': 'I understand.'},
        {'role': 'user', 'content': 'Explain gravity briefly.'},
        {'role': 'assistant', 'content': 'Gravity attracts objects with mass toward one another.'},
        {'role': 'user', 'content': 'And eclipses?'},
        {'role': 'assistant', 'content': 'An eclipse occurs when one celestial body blocks light from reaching another.'},
        {'role': 'user', 'content': 'Thanks.'},
        {'role': 'assistant', 'content': 'You are welcome.'},
    ], 'expected': []},
    {'id': 'real-read-preserved', 'text': '¿Qué ventana está activa ahora?', 'history': history, 'expected': ['baxy_window__active']},
]
for case in cases:
    case['history'] = _bounded_history(case['history'])
    case['payloads'] = {}
    for variant, prior in [('last-six', case['history'][-6:]), ('bounded-history', case['history'])]:
        payload = copy.deepcopy(original)
        payload['messages'][-1]['content'] = json.dumps({
            'previous_dialogue_for_references_only': prior,
            'current_request_to_interpret': case['text'],
        }, ensure_ascii=False)
        case['payloads'][variant] = payload
assert cases[0]['payloads']['last-six'] == original
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

manifest_hash = sha(manifest)
assert sha(model) == '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
prereg = {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Eight fixed native selector controls. Compare the last-six-message cut against the existing bounded history (12 messages,6000 chars), with identical JSON reference envelope,tools,sampling,template and system instructions. Actual355 request20 baseline equality asserted. Reconstruct full history from its published events and verify the last six are exactly captured. Seven added controls are synthetic development controls, not human acceptance. No tool execution,source edits,UI,voice or model promotion.',
    'hypothesis': 'The second truncation discards the original human name declaration while keeping several assistant memory status messages. Remove only that truncation if native controls improve without regressions. Do not infer the personal name from the account or rewrite the user question.',
    'inheritance': 'Carter_v2 LLM_CONTEXT_MEMORY_REPORT R1-R4 warns against assistant identity contamination and history repetition. Current316/317 and65 tested envelope/removal; their failures do not justify removing history or changing roles. Exact Qwen3.5 template77 and model350 research reused from INVESTIGACION_MODELO_C03.md / INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md. This test changes history completeness only.',
    'criteria': 'Read every native response. Personal context and assistant identity require no computer read; explicit Windows/process account and active window retain their requested reads. Fresh quien soy retains previously adopted account-read criterion without claiming the account is a verified personal name. Selection alone does not prove downstream answer quality.',
    'cases': cases,
    'pins': {str(path): sha(path) for path in [manifest, model, Path(config['llama_server']), root / 'src/baxy_mind/llm.py', Path(__file__), source / 'http-posts.jsonl', source / 'capture/events.jsonl']},
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
        for variant, payload in case['payloads'].items():
            client.begin_request(40)
            try:
                response = client._post(copy.deepcopy(payload))
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
