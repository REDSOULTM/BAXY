"""Follow failed catalog271 with one history ablation, no source adoption."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import urllib.request

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-history272'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
rows = [json.loads(line) for line in (private / 'C03-ui263-private/http-posts.jsonl').read_text(encoding='utf-8').splitlines()]
payload = next(row['payload'] for row in rows if row.get('stage') == 'request' and row.get('id') == 5)
hello = json.loads((private / 'C03-app-catalog262-private/HELLO_CATALOGS.json').read_text(encoding='utf-8'))
op = next(item for item in hello['capabilities'] if item['name'] == 'app.open')
payload['tools'][-1] = {'type': 'function', 'function': {'name': 'baxy_app__open', 'description': op['description'],
    'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}}}
current = json.loads(payload['messages'][-1]['content'])['current_request_to_interpret']
payload['messages'][-1]['content'] = current
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'hypothesis': 'Old verified-state prose suppresses a repeated explicit request even when app.open is visible.',
    'method': 'Same app_open_visible packet271, only previous dialogue removed. Current literal unchanged. Native selection only; no effects. Diagnostic ablation, not a proposal to erase all dialogue.',
    'criteria': 'Select only baxy_app__open after abstention in271.', 'payload': payload,
    'baseline': 'astra-catalog271/RESULT.json', 'backendPid': 89232}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
with urllib.request.urlopen('http://127.0.0.1:57485/slots', timeout=5) as response:
    assert not any(row['is_processing'] for row in json.load(response)), 'Backend busy.'
request = urllib.request.Request('http://127.0.0.1:57485/v1/chat/completions',
    data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(request, timeout=90) as response:
    result = json.load(response)
(out / 'RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result['choices'][0], ensure_ascii=False))
