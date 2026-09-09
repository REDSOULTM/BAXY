"""Same three requests296, adopted question scope, unchanged native backend."""
from pathlib import Path
import copy
import json
import sys
import urllib.request

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'src'))
from baxy_mind import llm

out = root/'artifacts/comprobaciones/C03/astra-question-scope298'
baseline = json.loads((root/'artifacts/comprobaciones/C03/astra-memory296/RESULT.json').read_text(encoding='utf-8'))
class Runtime(llm.LlmRuntime):
    def __init__(self, row, replay):
        self._gguf = row['posts'][0]['response']['model']
        self.responses = iter(row['posts'])
        self.replay = replay
        self.posts = []
    def _post(self, payload):
        payload = copy.deepcopy(payload)
        prefix = []
        for message in payload['messages']:
            if message['role'] != 'system':
                break
            prefix.append(message['content'])
        if len(prefix) > 1:
            payload['messages'] = [{'role': 'system', 'content': '\n\n'.join(prefix)}, *payload['messages'][len(prefix):]]
        if self.replay:
            response = copy.deepcopy(next(self.responses)['response'])
        else:
            with urllib.request.urlopen('http://127.0.0.1:63490/slots', timeout=5) as response:
                assert not any(item['is_processing'] for item in json.load(response))
            req = urllib.request.Request('http://127.0.0.1:63490/v1/chat/completions',
                data=json.dumps(payload, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=90) as response:
                response = json.load(response)
        self.posts.append({'payload': payload, 'response': response})
        return response

results = []
for row in baseline:
    for replay in (True, False):
        runtime = Runtime(row, replay)
        result = {'request': row['request'], 'replay': replay}
        try:
            result['answer'] = runtime.chat(row['request'], temperature=0.0,
                conversation_kind='knowledge', response_language='en' if row['request'].startswith('my ') else 'es')[0]
        except Exception as error:
            result.update(error=repr(error), audit_reason=getattr(error, 'audit_reason', None))
        result['posts'] = runtime.posts
        result['first_payload_equal296'] = runtime.posts[0]['payload'] == row['posts'][0]['payload']
        results.append(result)
        (out/'NATIVE_RESULT.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({k: v for k,v in result.items() if k != 'posts'}, ensure_ascii=True), flush=True)
