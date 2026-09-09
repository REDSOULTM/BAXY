"""Test preservation of a Core-observed account name in owner session264."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import json
import os
import re
import sys
import urllib.request

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind import llm

out = root / 'artifacts/comprobaciones/C03/astra-identity283'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
audit = [json.loads(line) for line in (private / 'C03-owner264-snapshot268/compose-audit.jsonl').read_text(encoding='utf-8').splitlines()]
row = next(row for row in audit if row.get('trace') == 't56' and row.get('published'))
facts = {'situation': json.loads(row['situation'])}
request_text = 'quien soy'
original = llm._payload_fact_defect
def preserve_account(text, payload):
    defect = original(text, payload)
    seen = payload.get('seen')
    account = seen.get('userName') if isinstance(seen, dict) else None
    if not defect and isinstance(account, str) and account.strip() and not re.search(
        r'(?<!\w)' + re.escape(account.casefold()) + r'(?!\w)', text.casefold()):
        return 'missing_name'
    return defect
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'evidence': 'UI collection282 index108 says Hola, soy BAXY. t56 audit contains verified system.identity with observed userName. The draft omits that current fact and answers with the wrong identity.',
    'hypothesis': 'Existing payload fact-preservation guard checks clock/volume but not observed account identity. Reusing missing_name for the dynamic observed userName can recover a useful statement without new wording or prompt.',
    'method': 'Same actual283 request and typed situation, current compose source267, existing backend. Compare original guard and one observed-field obligation; unchanged first prompt/settings. No operation or UI effects. Proposal only until native and owner tests pass.',
    'criteria': 'Reply names the actual OS account as the person/account, not assistant; no claim that personal-name memory was saved. No fixed answer, user-name constant or blanket BAXY phrase blacklist.',
    'facts': facts, 'request': request_text, 'originalDraftDefect': original(row['draft'], row['payload'])}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
class Runtime(llm.LlmRuntime):
    def __init__(self):
        self._gguf = r'D:\BAXYRuntime\experiments\models\qwen35-4b-e87f1764\Qwen3.5-4B-Q4_K_M.gguf'
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
        with urllib.request.urlopen('http://127.0.0.1:57485/slots', timeout=5) as response:
            assert not any(item['is_processing'] for item in json.load(response)), 'Backend busy.'
        request = urllib.request.Request('http://127.0.0.1:57485/v1/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
        self.posts.append({'payload': payload, 'response': result})
        return result
results = []
try:
    for variant, guard in [('before', original), ('preserve_observed_account', preserve_account)]:
        llm._payload_fact_defect = guard
        runtime = Runtime()
        try:
            answer = runtime.compose_user_message(request_text, 'status', facts)
            result = {'variant': variant, 'answer': answer, 'posts': runtime.posts}
        except Exception as error:
            result = {'variant': variant, 'error': type(error).__name__, 'detail': str(error), 'posts': runtime.posts}
        results.append(result)
        (out / 'RESULT.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({key:value for key,value in result.items() if key != 'posts'}, ensure_ascii=False), flush=True)
finally:
    llm._payload_fact_defect = original
assert results[0]['posts'][0]['payload'] == results[1]['posts'][0]['payload']
