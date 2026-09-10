"""Show actual model boundaries for694; never confuse raw_attempt with HTTP."""
import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--start', type=int, default=0)
parser.add_argument('--count', type=int, default=25)
args = parser.parse_args()
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-status-batch694-private'


def rows(name):
    with (private/name).open(encoding='utf-8-sig') as stream:
        return [json.loads(line) for line in stream]


http = rows('http-posts.jsonl')
boundary = rows('decision-boundary.jsonl')
replies = {(r['pid'], r['id']): r for r in http if r['stage'] in {'response', 'failure'}}
results = {(r['pid'], r['id']): r for r in boundary if r['stage'] in {'output', 'failure'}}
records = []
for entry in (r for r in boundary if r['stage'] == 'input'):
    terminal = results.get((entry['pid'], entry['id']))
    calls = []
    for request in http:
        if request['stage'] != 'request' or request['pid'] != entry['pid']:
            continue
        if request['time'] < entry['time'] or terminal is None or request['time'] > terminal['time']:
            continue
        payload = request['payload']
        reply = replies.get((request['pid'], request['id']))
        native = reply.get('response', {}) if reply else {}
        calls.append({'native_id': request['id'],
            'schema': payload.get('response_format', {}).get('json_schema', {}).get('name'),
            'last_user': next((m['content'] for m in reversed(payload.get('messages', [])) if m['role'] == 'user'), None),
            'choices': native.get('choices'),
            'failure': reply if reply and reply['stage'] == 'failure' else None})
    records.append({'id': entry['id'], 'text': entry['text'], 'evidence': entry.get('evidence'),
        'candidate_operations': [r.get('operation', r.get('name')) for r in entry.get('candidates', [])],
        'runtime_result': terminal, 'native_calls_started_during_decision': calls})
(private/'native-boundary-review.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
for row in records[args.start:args.start+args.count]:
    compact = {k: v for k, v in row.items() if k != 'native_calls_started_during_decision'}
    compact['calls'] = [{k: v for k, v in call.items() if k != 'last_user'} for call in row['native_calls_started_during_decision']]
    print(json.dumps(compact, ensure_ascii=False))
print(json.dumps({'decisions': len(records), 'native_requests': sum(r['stage']=='request' for r in http),
    'attribution': 'Native requests started inside the recorded decide_turn interval. Payload text is retained for confirmation; deferred work may finish later. No attribution by audit row position.'}))
