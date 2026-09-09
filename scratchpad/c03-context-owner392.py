"""Measure the existing contextual resolver on frozen history questions, no source edits."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind import llm

out = root / 'artifacts/comprobaciones/C03/astra-context-owner392'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-context-owner392-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
all_cases = json.loads((root / 'scratchpad/c03-native-generalization385-cases.json').read_text(encoding='utf-8'))['cases']
cases = [case for case in all_cases if case['history']]
assert len(cases) == 10
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
    'method': 'Ten history-bearing cases from frozen17 set385, no new cases. Call the existing LlmRuntime._resolve_contextual_answer with unchanged production prompt/schema/bounds/retries. Capture both its response and current general observation/language guard verdicts, without treating those guards as a semantic oracle. No operation, source/prompt change, private dispatch, full mind, App/UI/voice or fresh-human acceptance.',
    'reason': '387 descriptor and391 native no-tool instruction did not improve identity; do not repeat prompt variants.3909B no-mmap fits isolated resources but still2/4 and echoes assistant history, so no promotion. Inherit the already implemented semantic reference resolver instead of designing a new name cache or operation; inspect its behavior before any routing decision. Its current use is literal recall/followup, not all knowledge. It can return resolved_meaning as fallback and is not by itself a factual guarantee.',
    'criteria': 'Retain human self-name, latest correction and third-party separation; identify BAXY only when asked about BAXY. Explicit saved-memory request cannot be answered as though a conversational name were persisted. A schema-valid explanation of the request is not the answer; silence/errors fail. No acceptance solely because the helper returns nonempty text.',
    'model': str(model), 'model_sha256': sha(model), 'manifest_sha256': sha(manifest),
    'backend_sha256': sha(config['llama_server']), 'source_sha256': sha(root / 'src/baxy_mind/llm.py'), 'private': str(private)}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
class Capture(llm.LlmRuntime):
    case = None
    def _post(self, payload, *args, **kwargs):
        response = super()._post(payload, *args, **kwargs)
        with (private / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'id': self.case['id'] if self.case else None, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
        return response
client = Capture()
try:
    client.start_warmup()
    assert client.wait_warmup(90)
    for case in cases:
        client.case = case
        before = time.monotonic()
        client.begin_request(40)
        try:
            answer = client._resolve_contextual_answer(history=case['history'], current=case['request'])
            row = {'id': case['id'], 'answer': answer,
                'unread_machine_claim': llm.visible_reply_asserts_an_unread_machine_state(answer, request=case['request']),
                'opposite_language': llm._reply_uses_opposite_language(answer, llm.read_request(case['request']).language)}
        except Exception as error:
            row = {'id': case['id'], 'error': type(error).__name__, 'detail': str(error)}
        finally:
            client.end_request()
        row['seconds'] = round(time.monotonic()-before, 3)
        with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(json.dumps(row, ensure_ascii=True), flush=True)
finally:
    client.close()
assert sha(manifest) == prereg['manifest_sha256']
