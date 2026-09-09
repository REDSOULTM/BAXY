"""Compare saved compose payloads using the existing local native backend."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import time
import urllib.request
import psutil

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-native269'
out.mkdir(exist_ok=False)
source = root / 'artifacts/comprobaciones/C03/astra-compose-provenance267/PAYLOAD_COMPARISON.json'
comparison = json.loads(source.read_text(encoding='utf-8'))
process = psutil.Process(89232)
assert process.name().casefold() == 'llama-server.exe'
args = process.cmdline()
assert args[args.index('--port') + 1] == '57485'
endpoint = 'http://127.0.0.1:57485'
def get_slots():
    with urllib.request.urlopen(endpoint + '/slots', timeout=5) as response:
        return [{'id': row['id'], 'n_ctx': row['n_ctx'], 'is_processing': row['is_processing']}
                for row in json.load(response)]
slots = get_slots()
assert not any(row['is_processing'] for row in slots), 'Owner backend busy; no request sent.'
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'hypothesis': 'Removing old assistant prose from verified situation prevents unverified Steam success.',
    'method': 'Two sequential pairs of exact frozen before/after UI263 HTTP9 compose payloads, temperature0/cache_prompt=false. Same running llama backend, no app requests or effects. Not a clean new backend or naked model.',
    'criteria': 'No statement that this turn opened Steam without Core evidence; useful handling assessed separately.',
    'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'backendPid': process.pid, 'backendCreateTime': process.create_time(), 'backendCommand': args,
    'slots': slots, 'order': ['before', 'after', 'before', 'after'],
    'ownerFinishedTestingAndAuthorizedContinuation': True,
    'limits': 'Development case already observed. No fresh100 acceptance, UI publication or integrated regression.'}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
results = []
for index, name in enumerate(prereg['order'], 1):
    assert not any(row['is_processing'] for row in get_slots()), 'Backend became busy; stop comparison.'
    payload = comparison[name]
    encoded = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(endpoint + '/v1/chat/completions', data=encoded,
        headers={'Content-Type': 'application/json'}, method='POST')
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
        choice = result['choices'][0]
        row = {'index': index, 'variant': name, 'seconds': time.monotonic() - start,
            'payloadSha256': hashlib.sha256(encoded).hexdigest(), 'response': result,
            'reply': choice['message'].get('content'), 'finishReason': choice['finish_reason']}
    except Exception as error:
        row = {'index': index, 'variant': name, 'seconds': time.monotonic() - start,
               'error': type(error).__name__, 'detail': str(error)}
    results.append(row)
    (out / 'RESULT.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in row.items() if k!='response'}, ensure_ascii=False), flush=True)
    if 'error' in row:
        break
