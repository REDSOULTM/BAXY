"""Send actual276 shortlists through production native selector unchanged."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import sys
import urllib.request

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind.llm import LlmRuntime

out = root / 'artifacts/comprobaciones/C03/astra-native277'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
hello = json.loads((private / 'C03-app-catalog262-private/HELLO_CATALOGS.json').read_text(encoding='utf-8'))
contracts = {item['name']: {'description': item['description']} for item in hello['capabilities']}
rows = json.loads((root / 'artifacts/comprobaciones/C03/astra-entity276/RESULT.json').read_text(encoding='utf-8'))
wire = [json.loads(line) for line in (private / 'C03-ui263-private/http-posts.jsonl').read_text(encoding='utf-8').splitlines()]
old = next(row['payload'] for row in wire if row.get('stage') == 'request' and row.get('id') == 5)
history = json.loads(old['messages'][-1]['content'])['previous_dialogue_for_references_only']
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'method': 'Use real native selector implementation with typed_entity shortlists276, original literal and full saved history. Only retrieval candidates/order differ from prior tests; no operations executed.',
    'criteria': 'Only app.open for all three known development requests.', 'source': 'astra-entity276/RESULT.json', 'backendPid': 89232}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
class Runtime(LlmRuntime):
    def __init__(self):
        self.posts = []
    def _post(self, payload):
        with urllib.request.urlopen('http://127.0.0.1:57485/slots', timeout=5) as response:
            assert not any(row['is_processing'] for row in json.load(response)), 'Backend busy.'
        request = urllib.request.Request('http://127.0.0.1:57485/v1/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
        self.posts.append({'payload': payload, 'response': result})
        return result
runtime = Runtime()
results = []
for row in rows:
    if row['variant'] != 'typed_entity':
        continue
    decision = runtime._post_native_tool_selection(row['input'], row['shortlist'], contracts, history)
    results.append({'input': row['input'], 'decision': decision, 'post': runtime.posts[-1]})
    (out / 'RESULT.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'input': row['input'], 'decision': decision}, ensure_ascii=False), flush=True)
