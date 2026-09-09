"""Locate selector loss with the omitted authenticated app.open leaf restored."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import urllib.request
import time

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-catalog271'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
wire = private / 'C03-ui263-private/http-posts.jsonl'
rows = [json.loads(line) for line in wire.read_text(encoding='utf-8').splitlines()]
original = next(row['payload'] for row in rows if row.get('stage') == 'request' and row.get('id') == 5)
hello_path = private / 'C03-app-catalog262-private/HELLO_CATALOGS.json'
hello = json.loads(hello_path.read_text(encoding='utf-8'))
operation = next(item for item in hello['capabilities'] if item['name'] == 'app.open')
changed = copy.deepcopy(original)
assert not any(tool['function']['name'] == 'baxy_app__open' for tool in changed['tools'])
changed['tools'][-1] = {'type': 'function', 'function': {'name': 'baxy_app__open',
    'description': operation['description'],
    'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}}}
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'hypothesis': 'Native selector can retain app.open when the retrieval omission is removed.',
    'method': 'Exact UI263 HTTP5 before/after; replace only last candidate with authenticated app.open, retaining28 tools. Same history, current literal, system, sampling and backend. Diagnostic oracle intervention, NOT a deployable retrieval algorithm.',
    'criteria': 'After selects only app.open; before reproduces no selection. No operation executes.',
    'catalogSha256': hashlib.sha256(hello_path.read_bytes()).hexdigest(),
    'wireSha256': hashlib.sha256(wire.read_bytes()).hexdigest(),
    'replacedTool': original['tools'][-1]['function']['name'],
    'backend': 'http://127.0.0.1:57485', 'backendPid': 89232,
    'limits': 'Development case; no argument grounding, UI or acceptance claim.'}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
results = []
for variant, payload in [('before', original), ('app_open_visible', changed)]:
    with urllib.request.urlopen(prereg['backend'] + '/slots', timeout=5) as response:
        assert not any(row['is_processing'] for row in json.load(response)), 'Backend busy.'
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(prereg['backend'] + '/v1/chat/completions', data=data,
        headers={'Content-Type': 'application/json'}, method='POST')
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.load(response)
    row = {'variant': variant, 'seconds': time.monotonic() - start, 'response': result,
        'payloadSha256': hashlib.sha256(data).hexdigest()}
    results.append(row)
    (out / 'RESULT.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'variant': variant, 'seconds': row['seconds'], 'choice': result['choices'][0]}, ensure_ascii=False), flush=True)
