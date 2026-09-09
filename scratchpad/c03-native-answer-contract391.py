"""Align the native no-tool answer contract on eight captured primaries, no source edits."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind.llm import LlmRuntime

out = root / 'artifacts/comprobaciones/C03/astra-native-answer-contract391'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-native-answer-contract391-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
source = private.parent / 'C03-native-generalization386-private/http-posts.jsonl'
wire = [row for row in map(json.loads, source.open(encoding='utf-8-sig')) if row.get('stage') == 'request']
ids = {3: 't10', 9: 'explicit-persistence', 13: 'product380-t9', 17: 'assistant-identity',
    21: 'human-identity-es', 24: 'mixed-self-name', 31: 'air-composition', 35: 'capital-france'}
cases = [{'id': ids[row['id']], 'reference': row['payload']} for row in wire if row['id'] in ids]
assert len(cases) == 8 and all(len(c['reference']['tools']) == 28 for c in cases)
old = 'If no function applies, keep any text to one brief sentence; a separate conversational stage answers the person.'
new = "If no function applies, answer the person's current question or request directly and briefly as BAXY, using the conversation."
assert all(c['reference']['messages'][0]['content'].count(old) == 1 for c in cases)
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases, 'old': old, 'new': new,
    'method': 'Eight exact native primary payloads386, each paired baseline and change of the final no-function sentence only. Every preceding selector rule, current-user-data instruction, tool/argument contract, history, sampler, token limit, model and template handling remain identical. These are native responses with BAXY prompt, not guarded full mind or product. No effects, source change, fresh humans, UI, voice or promotion.',
    'reason': '383 now retains the primary draft under chat guards, but its native instruction still delegates answering to another stage.3909B switches from wrong account read to repeating the prior assistant statement, still2/4 and no accuracy gain;387 clearer account description also2/4. Align the actual no-tool responsibility with the Qwen3.5 template, which directs answering normally without a function. Test this boundary rather than add identity-name rules or adopt a larger model without gain.',
    'criteria': 'Preserve five useful primaries (Alvaro name, BAXY identity, Lucia name, air not water, Paris); improve actual human identity questions using supplied Alvaro/Eva, not BAXY/Windows/absence. Explicit persistence stays failed unless supported by a real available operation; cannot claim saved content from history. Judge content and concision, never only no-call rate.',
    'research': ['https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/chat_template.jinja', 'https://github.com/ggml-org/llama.cpp/blob/b9980/docs/function-calling.md'],
    'model': str(model), 'model_sha256': sha(model), 'manifest_sha256': sha(manifest),
    'backend_sha256': sha(config['llama_server']), 'private': str(private)}
assert prereg['model_sha256'] == '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
client = LlmRuntime()
try:
    client.start_warmup()
    assert client.wait_warmup(90)
    for case in cases:
        for variant in ['baseline', 'direct-native-answer']:
            payload = copy.deepcopy(case['reference'])
            if variant != 'baseline':
                payload['messages'][0]['content'] = payload['messages'][0]['content'].replace(old, new)
            before = time.monotonic()
            client.begin_request(40)
            try:
                response = client._post(payload)
            finally:
                client.end_request()
            with (private / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'id': case['id'], 'variant': variant, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
            row = {'id': case['id'], 'variant': variant, 'seconds': round(time.monotonic()-before, 3), 'choice': response['choices'][0]}
            with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(json.dumps(row, ensure_ascii=True), flush=True)
finally:
    client.close()
assert sha(manifest) == prereg['manifest_sha256']
