"""Isolate the missing dialogue in actual disabled-memory error composition."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind.llm import LlmRuntime

base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
source = base / 'C03-memory-product366-private'
out = root / 'artifacts/comprobaciones/C03/astra-recall-dialogue372'
private = base / 'C03-recall-dialogue372-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
audits = [json.loads(l) for l in (source / 'compose-audit.jsonl').open(encoding='utf-8-sig')]
wire = [json.loads(l) for l in (source / 'http-posts.jsonl').open(encoding='utf-8-sig')]
histories = {}
history = []
turn = 0
for line in (source / 'capture/events.jsonl').open(encoding='utf-8-sig'):
    row = json.loads(line)
    if row.get('type') != 'event' or row['event'].get('type') != 'activity':
        continue
    entry = row['event']['entry']
    if entry['src'] == 'YOU':
        turn += 1
        histories[f't{turn}'] = {'request': entry['msg'], 'history': copy.deepcopy(history[-11:])}
        history.append({'role': 'user', 'content': entry['msg']})
    elif entry['src'] == 'BAXY':
        history.append({'role': 'assistant', 'content': entry['msg']})
cases = []
for trace in ['t5', 't10']:
    audit = next(r for r in audits if r.get('trace') == trace and r.get('stage') == 'first')
    fragment = histories[trace]['request'] + '\nsituation: ' + json.dumps(audit['payload'], ensure_ascii=False)
    reference = next(r['payload'] for r in wire if r.get('stage') == 'request' and r['payload']['messages'][-1].get('content', '').startswith(fragment))
    cases.append({'id': trace, 'reference': reference, **histories[trace], 'expected': 'Use the current human declaration (Jordan/Álvaro); memory.recall failed, no assertion of persistence.'})
for label, dialogue, request, expected in [
    ('third-party', [{'role': 'user', 'content': 'My coworker is Morgan.'}, {'role': 'assistant', 'content': 'Morgan is your coworker.'}], 'What is my name?', 'Name is not supplied. Never assign the coworker name to the user.'),
    ('assistant-conflict', [{'role': 'user', 'content': 'My name is Jordan.'}, {'role': 'assistant', 'content': 'Your name is Morgan.'}], 'What is my name?', 'Human declaration Jordan outranks the incorrect assistant statement Morgan.'),
    ('explicit-persistence', [{'role': 'user', 'content': 'My name is Jordan.'}, {'role': 'assistant', 'content': 'Hello Jordan.'}], 'What name have you saved in private memory?', 'Cannot verify a stored name because memory is disabled. A conversational name does not establish persistence.'),
]:
    reference = copy.deepcopy(cases[0]['reference'])
    message = reference['messages'][-1]
    message['content'] = request + '\nsituation: ' + message['content'].split('\nsituation: ', 1)[1]
    cases.append({'id': label, 'reference': reference, 'history': dialogue, 'request': request, 'expected': expected})
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
assert sha(model) == '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
    'method': 'Five development cases: two exact366 error requests plus three explicitly synthetic provenance/persistence controls. Same Qwen3.5 and exact first compositor payload, full native dialogue371 versus the same bounded human messages with assistant utterances removed. No fabricated extracted fact or summary; current request unchanged.371 failed Spanish and human/assistant conflict, so test provenance rather than another instruction. No new prose, cause, language, operation result, sampler, source, effect or runtime promotion. First native completions only; guards and App not tested by this replay.',
    'first_loss': 'NaturalMemoryRequestParser routes generic name questions to memory.recall even with a current declaration. MainWindowViewModel AddMessage / ModelMessageComposer.CreateFacts omit priorRequests and previousAnswer for error. The actual366 compositor receives memory_disabled and no declaration; HTTP34 disproves masking of the user declaration in the separate selector.',
    'inheritance': 'Carter_v2/LLM_CONTEXT_MEMORY_REPORT.md human provenance; INVESTIGACION_FORMATO_Y_CLASIFICACION_C03;361 native role dialogue validated on Qwen3.5 selector, not yet this compositor.347 tested operation/tool result roles, not this failure with human dialogue. No repetition of failed provenance annotations.',
    'criteria': 'Answer the name from human dialogue while accurately limiting failure to private recall. Never infer identity from a third party or an assistant-only claim. Explicit persistent-memory query must not receive a fabricated saved result. Score each case, including any useful baseline unknown answer when no dialogue is provided.',
    'model': str(model), 'model_sha256': sha(model), 'manifest_sha256': sha(manifest), 'backend_sha256': sha(config['llama_server']), 'private': str(private)}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
client = LlmRuntime()
try:
    client.start_warmup()
    assert client.wait_warmup(90)
    (out / 'command.json').write_text(json.dumps(client._server_command(), indent=2) + '\n', encoding='utf-8')
    for case in cases:
        for variant in ['native-dialogue', 'human-dialogue']:
            payload = copy.deepcopy(case['reference'])
            dialogue = case['history'] if variant == 'native-dialogue' else [m for m in case['history'] if m['role'] == 'user']
            payload['messages'][-1:-1] = copy.deepcopy(dialogue)
            client.begin_request(40)
            try:
                response = client._post(payload)
            finally:
                client.end_request()
            result = {'id': case['id'], 'variant': variant, 'answer': response['choices'][0]['message'].get('content'), 'finish_reason': response['choices'][0]['finish_reason']}
            with (private / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({**result, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
            with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(result, ensure_ascii=False) + '\n')
            print(json.dumps(result, ensure_ascii=True), flush=True)
finally:
    client.close()
assert sha(manifest) == prereg['manifest_sha256']
