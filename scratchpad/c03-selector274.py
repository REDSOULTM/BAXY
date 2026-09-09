"""Use the real native description builder omitted by diagnostic271."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import json
import os
import sys
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind.llm import _native_selection_description

out = root / 'artifacts/comprobaciones/C03/astra-selector274'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
rows = [json.loads(line) for line in (private / 'C03-ui263-private/http-posts.jsonl').read_text(encoding='utf-8').splitlines()]
original = next(row['payload'] for row in rows if row.get('stage') == 'request' and row.get('id') == 5)
hello = json.loads((private / 'C03-app-catalog262-private/HELLO_CATALOGS.json').read_text(encoding='utf-8'))
op = next(item for item in hello['capabilities'] if item['name'] == 'app.open')
app = {'type': 'function', 'function': {'name': 'baxy_app__open',
    'description': _native_selection_description('app.open', op['description']),
    'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}}}
full = copy.deepcopy(original)
full['tools'][-1] = app
single = copy.deepcopy(full)
single['tools'] = [app]
simple = copy.deepcopy(single)
content = json.loads(simple['messages'][-1]['content'])
content['current_request_to_interpret'] = 'abre steam'
simple['messages'][-1]['content'] = json.dumps(content, ensure_ascii=False)
variants = [('actual_description_28', full), ('actual_description_only_app', single), ('simple_control_only_app', simple)]
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'correction': '271/272 appended the Core description directly, omitting the existing native-selection suffix. Their non-selection does not prove what the real app.open native tool would do.',
    'method': 'First restore omitted actual suffix using production helper; then remove competing tools only; then simple owner literal control. Keep real history/system/sampling. No new product prompt, descriptions or operations.',
    'criteria': 'Select app.open and no other function; tool calls only, no effects.',
    'limits': 'Diagnostic candidate injection; retrieval algorithm and grounding remain unproven.',
    'backendPid': 89232, 'variants': [{'name': name, 'payload': payload} for name, payload in variants]}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
results = []
for name, payload in variants:
    with urllib.request.urlopen('http://127.0.0.1:57485/slots', timeout=5) as response:
        assert not any(row['is_processing'] for row in json.load(response)), 'Backend busy.'
    request = urllib.request.Request('http://127.0.0.1:57485/v1/chat/completions',
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.load(response)
    row = {'variant': name, 'seconds': time.monotonic() - start, 'response': result}
    results.append(row)
    (out / 'RESULT.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'variant': name, 'choice': result['choices'][0]}, ensure_ascii=False), flush=True)
