"""Keep all28 actual tools and change only the rank of app.open."""
from pathlib import Path
from datetime import datetime, timezone
import json
import urllib.request

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-order275'
out.mkdir(exist_ok=False)
prereg274 = json.loads((root / 'artifacts/comprobaciones/C03/astra-selector274/PREREG.json').read_text(encoding='utf-8'))
payload = prereg274['variants'][0]['payload']
assert payload['tools'][-1]['function']['name'] == 'baxy_app__open'
payload['tools'] = [payload['tools'][-1], *payload['tools'][:-1]]
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Exact actual_description_28 of274, only move app.open from last to first. Same28 tools, full original history, request, descriptions, sampling and server.',
    'hypothesis': 'Retrieval rank controls native tool attention; correct app identity can support ranking without reducing available effects.',
    'criteria': 'Only app.open selected. Diagnostic order oracle, no deployable algorithm yet.', 'payload': payload}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
with urllib.request.urlopen('http://127.0.0.1:57485/slots', timeout=5) as response:
    assert not any(row['is_processing'] for row in json.load(response)), 'Backend busy.'
request = urllib.request.Request('http://127.0.0.1:57485/v1/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(request, timeout=90) as response:
    result = json.load(response)
(out / 'RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result['choices'][0], ensure_ascii=False))
