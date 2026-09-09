"""Inspect saved UI263 packets only; leave the owner's UI264 entirely alone."""
from pathlib import Path
import json
import os

root = Path(__file__).resolve().parents[1]
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui263-private/http-posts.jsonl'
rows = [json.loads(line) for line in private.read_text(encoding='utf-8').splitlines()]
requests = {row['id']:row for row in rows if row['stage']=='request'}
for row in rows:
    if row['stage'] != 'response':
        continue
    choices = row.get('response', {}).get('choices', [])
    if not choices:
        continue
    answer = choices[0].get('message', {}).get('content', '')
    if row['id'] in (5,7) or 'Ya he abierto Steam' in answer:
        payload = requests[row['id']]['payload']
        print(json.dumps({'id':row['id'], 'messages':payload.get('messages'),
            'tools':[tool['function']['name'] for tool in payload.get('tools', [])],
            'answer':answer, 'finishReason':choices[0].get('finish_reason'),
            'settings':{k:v for k,v in payload.items() if k not in ('messages','tools')}},
            ensure_ascii=False))
audit = root/'artifacts/comprobaciones/C03/astra-ui263/compose-audit.jsonl'
for line in audit.read_text(encoding='utf-8').splitlines():
    row = json.loads(line)
    if 'Tengo en mente' in line or 'Ya he abierto Steam' in line:
        print(json.dumps({'composeAudit':row}, ensure_ascii=False))
