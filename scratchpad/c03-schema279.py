"""Compare real native argument schemas to empty selection tools, no effects."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-schema279'
out.mkdir(exist_ok=False)
before_path = root / 'artifacts/comprobaciones/C03/astra-priority278/RESULT.json'
before = json.loads(before_path.read_text(encoding='utf-8'))
hello_path = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-app-catalog262-private/HELLO_CATALOGS.json'
hello = json.loads(hello_path.read_text(encoding='utf-8'))
schemas = {item['name']: item['argumentsSchema'] for item in hello['capabilities']}
case_ids = ['owner-1', 'owner-2', 'owner-3', 'win-07', 'med-04', 'app-05', 'cmp-01']
removed = 'Function arguments are extracted and validated in a later stage, so the declared functions take no arguments here. '
cases = []
for case_id in case_ids:
    row = next(row for row in before if row['case_id'] == case_id and row['variant'] == 'app_identity_priority')
    payload = copy.deepcopy(row['post']['payload'])
    assert removed in payload['messages'][0]['content']
    payload['messages'][0]['content'] = payload['messages'][0]['content'].replace(removed, '')
    for tool in payload['tools']:
        operation = tool['function']['name'].removeprefix('baxy_').replace('__', '.')
        tool['function']['parameters'] = copy.deepcopy(schemas[operation])
    cases.append({'case_id': case_id, 'input': row['input'], 'baselineDecision': row['decision'], 'payload': payload})
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'hypothesis': 'Removing the real parameter contract from native tools weakens semantic distinction; native full schema may recover correct selection and literal target.',
    'method': 'Seven frozen278 cases with identical28 tool names/order/descriptions, request/history and sampler. Single conceptual contract change: replace empty parameters with exact Core schemas and remove only the now-contradictory two-sentence argument-defer instruction. No replacement instruction, examples, template or tool_choice changes. No execution.',
    'criteria': 'owner1/2/3 app.open; win07 window.application.status; med04 media.play.query; app05 app.installed; cmp01 app.open plus media.play.query. Returned arguments independently inspected; no guessed identity accepted as execution authority.',
    'inheritance': ['INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md', 'biblioteca/carter/legacy/Carter_v2/TOOL_CALL_COMPATIBILITY_AUDIT.md', 'biblioteca/gemma4-agent/documentacion/02_router/research/1_toolcalling.md'],
    'primarySource': 'https://qwen.readthedocs.io/en/latest/framework/function_call.html',
    'scopeDifference': 'Qwen3 guide establishes schema protocol; exact Qwen3.5-4B/b9980 behavior must be measured locally.',
    'sourceHashes': {'baseline': hashlib.sha256(before_path.read_bytes()).hexdigest(), 'hello': hashlib.sha256(hello_path.read_bytes()).hexdigest()},
    'backendPid': 89232, 'cases': cases, 'freshAcceptance': False}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
results = []
for case in cases:
    with urllib.request.urlopen('http://127.0.0.1:57485/slots', timeout=5) as response:
        assert not any(row['is_processing'] for row in json.load(response)), 'Backend busy.'
    request = urllib.request.Request('http://127.0.0.1:57485/v1/chat/completions',
        data=json.dumps(case['payload'], ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
        row = {'case_id': case['case_id'], 'seconds': time.monotonic() - started, 'response': result}
    except urllib.error.HTTPError as error:
        row = {'case_id': case['case_id'], 'seconds': time.monotonic() - started, 'httpStatus': error.code,
            'errorBody': error.read().decode('utf-8', errors='replace')}
    results.append(row)
    (out / 'RESULT.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'case_id': row['case_id'], 'choice': row.get('response', {}).get('choices'),
        'httpStatus': row.get('httpStatus'), 'errorBody': row.get('errorBody')}, ensure_ascii=False), flush=True)
