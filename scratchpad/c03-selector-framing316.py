"""Native replay: isolate JSON quoting and prior assistant greeting, no effects."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import time
import urllib.request
import psutil

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-selector-framing316'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-ui314-private'
capture = private / 'http-posts.jsonl'
rows = [json.loads(line) for line in capture.read_text(encoding='utf-8').splitlines()]
original = next(row['payload'] for row in rows if row['stage'] == 'request' and len(row['payload'].get('tools', [])) == 28)
embedded = json.loads(original['messages'][-1]['content'])
variants = []
for name in ['quoted_history', 'native_history', 'quoted_no_history', 'native_no_history']:
    payload = copy.deepcopy(original)
    history = embedded['previous_dialogue_for_references_only'] if name.endswith('_history') and not name.endswith('_no_history') else []
    if name.startswith('native'):
        payload['messages'] = [original['messages'][0], *history,
            {'role': 'user', 'content': embedded['current_request_to_interpret']}]
    else:
        payload['messages'][-1]['content'] = json.dumps({
            'previous_dialogue_for_references_only': history,
            'current_request_to_interpret': embedded['current_request_to_interpret']}, ensure_ascii=False)
    variants.append((name, payload))
assert variants[0][1] == original
backend = psutil.Process(97776)
assert abs(backend.create_time() - 1788833707.8377817) < .01
assert backend.cmdline()[backend.cmdline().index('--port') + 1] == '60333'
endpoint = 'http://127.0.0.1:60333'
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Four native HTTP replays of exact root314, isolating JSON envelope versus native user/assistant turns and prior greeting presence. Same system,28 descriptors,all request parameters. No BAXY guard or operation execution in this replay; UI315 stays open. Template/protocol inheritance: Qwen official function_call documentation and INVESTIGACION_FORMATO_Y_CLASIFICACION_C03. No new prompt or descriptor sweep.',
    'criteria': 'Compare first native selected operations, finish_reason and prose. An unchanged generic answer is not an improvement. A potential change requires prior18 controls before adoption; neither an OS identity nor any fact may be asserted without subsequent real read.',
    'capture': str(capture), 'captureSha256': hashlib.sha256(capture.read_bytes()).hexdigest(),
    'backend': {'pid': backend.pid, 'createTime': backend.create_time(), 'command': backend.cmdline()},
    'variants': [name for name, _ in variants]}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
results = []
for name, payload in variants:
    with urllib.request.urlopen(endpoint + '/slots', timeout=5) as response:
        assert not any(slot['is_processing'] for slot in json.load(response)), 'Owner/backend busy: stop diagnostic, preserve results.'
    request = urllib.request.Request(endpoint + '/v1/chat/completions',
        data=json.dumps(payload, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=60) as response:
        response = json.load(response)
    choice = response['choices'][0]
    result = {'variant': name, 'seconds': round(time.monotonic() - started, 3),
        'finish': choice['finish_reason'], 'message': choice['message'], 'payload': payload, 'response': response}
    results.append(result)
    (out / 'RESULT.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key not in {'payload', 'response'}}, ensure_ascii=True), flush=True)
