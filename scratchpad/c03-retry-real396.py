"""Fault diagnostic: preserve actual chat history on the existing bounded retry."""
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind import llm

out = root / 'artifacts/comprobaciones/C03/astra-retry-real396'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-retry-real396-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
all_cases = json.loads((root / 'scratchpad/c03-native-generalization385-cases.json').read_text(encoding='utf-8'))['cases']
ids = {'t5', 't10', 'third-party', 'corrected-self-name', 'capital-france'}
cases = [case for case in all_cases if case['id'] in ids]
assert len(cases) == 5
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
    'method': 'Fault diagnostic, not normal human acceptance. Five already frozen385 cases, four with name context and one no-history control. Force an explicitly synthetic opposite-language initial_reply so the existing production chat guard must repair it. Run actual source395 chat with no request/response modification hook. Compare with frozen baseline394; the source now retains its own scoped dialogue in bounded_chat_answer. Same model, original system/retry instruction, sampler, grammar, limits and all guards. No source modification, no new name parser or answer text, no selector or private-memory dispatch.',
    'reason': 'llm.chat currently retries with original system + repair instruction + language + last user, but drops every previous user/assistant message. Source395 adopts that retention after394 improved strict usefulness2/5 to4/5 plus one partial (Alvaro correct, false last-message timing);396 validates the real implementation. This is an observed transport loss, distinct from392 contextual semantic resolver (5/10 rejected) and371/372 memory-error composition (still2/5, rejected). Do not treat dialogue as persisted memory or strip assistant roles globally. Compare a one-line retention repair at the actual retry owner.',
    'criteria': 'Every injected wrong-language draft must actually reach bounded_chat_answer. Valid final names must follow human declarations/correction; third-party Morgan remains unknown, not the user; France remains Paris without history. Record final guards/errors and all raw requests, not only nonempty answers. Require improvement without regression before adopting. Fault cases remain separate from normal acceptance.',
    'model': str(model), 'model_sha256': sha(model), 'backend_sha256': sha(config['llama_server']),
    'manifest_sha256': sha(manifest), 'source_sha256': sha(root / 'src/baxy_mind/llm.py'), 'private': str(private)}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))

class Capture(llm.LlmRuntime):
    case = None
    variant = None
    retries = 0
    def _post(self, payload, *args, **kwargs):
        actual = copy.deepcopy(payload)
        schema_name = actual.get('response_format', {}).get('json_schema', {}).get('name')
        is_retry = schema_name == 'bounded_chat_answer'
        if is_retry:
            self.retries += 1
        response = super()._post(actual, *args, **kwargs)
        with (private / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'id': self.case['id'], 'variant': self.variant, 'is_retry': is_retry,
                'payload_before': payload, 'payload': actual, 'response': response}, ensure_ascii=False) + '\n')
        return response

client = Capture()
try:
    client.start_warmup()
    assert client.wait_warmup(90)
    for case in cases:
        language = llm.read_request(case['request']).language
        injected = ('Hola, soy un asistente virtual y estoy aquí para ayudarte con tus preguntas.'
                    if language == 'en' else
                    'Hello, I am a virtual assistant and I am here to help you with your questions.')
        assert llm._reply_uses_opposite_language(injected, language), (case['id'], language)
        for variant in ['source395']:
            client.case, client.variant, client.retries = case, variant, 0
            started = time.monotonic()
            client.begin_request(40)
            try:
                answer, calls = client.chat(history=case['history'], text=case['request'],
                    conversation_kind='knowledge', response_language=language, temperature=0,
                    initial_reply=injected)
                row = {'id': case['id'], 'variant': variant, 'answer': answer, 'calls': calls}
            except Exception as error:
                row = {'id': case['id'], 'variant': variant, 'error': type(error).__name__, 'detail': str(error)}
            finally:
                client.end_request()
            row.update(injected_draft=injected, retries=client.retries, seconds=round(time.monotonic()-started, 3))
            with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(json.dumps(row, ensure_ascii=True), flush=True)
finally:
    client.close()
assert sha(manifest) == prereg['manifest_sha256']
