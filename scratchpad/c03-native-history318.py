"""Check native message roles against the already measured 18 root controls."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import json
import time
import urllib.request
import psutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-native-history318'
out.mkdir(exist_ok=False)
cases = json.loads((base / 'astra-selector-model292/RESULT.json').read_text(encoding='utf-8'))
backend = psutil.Process(97776)
assert abs(backend.create_time() - 1788833707.8377817) < .01
endpoint = 'http://127.0.0.1:60333'
(out / 'PREREG.json').write_text(json.dumps({
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Exact18 controls292, same registered2507 backend profile, system,tools,settings. Only replace JSON request/history wrapper with native roles, preserving every prior message. No startup greeting exclusion in this test; native_history316 failed identity314, so this is a generalization check before considering any source change. No function runs, only native selection.',
    'criteria': 'Retain baseline292 correct actions and abstentions; inspect ordered operations and known alternatives individually. Any new scope error rejects representation as a standalone change. Do not change descriptors/prompt/models, and do not promote by count alone.',
    'backend': {'pid': backend.pid, 'createTime': backend.create_time(), 'command': backend.cmdline()},
    'cases': [row['case_id'] for row in cases],
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
results = []
for row in cases:
    payload = copy.deepcopy(row['payload'])
    embedded = json.loads(payload['messages'][-1]['content'])
    payload['messages'] = [payload['messages'][0], *embedded['previous_dialogue_for_references_only'],
        {'role': 'user', 'content': embedded['current_request_to_interpret']}]
    with urllib.request.urlopen(endpoint + '/slots', timeout=5) as response:
        assert not any(slot['is_processing'] for slot in json.load(response)), 'Owner/backend busy; preserve results and stop.'
    request = urllib.request.Request(endpoint + '/v1/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={'Content-Type': 'application/json'})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=60) as response:
        response = json.load(response)
    choice = response['choices'][0]
    operations = [call['function']['name'].removeprefix('baxy_').replace('__', '.')
        for call in choice['message'].get('tool_calls') or []]
    result = {'case_id': row['case_id'], 'expected': row['expected'], 'before': row['operations'],
        'after': operations, 'finish': choice['finish_reason'], 'seconds': round(time.monotonic() - started, 3),
        'payload': payload, 'response': response}
    results.append(result)
    (out / 'RESULT.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key not in {'payload', 'response'}}, ensure_ascii=True), flush=True)
