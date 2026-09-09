from pathlib import Path
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-files86-negation'
rows = [json.loads(s) for s in (out / 'wire-19416.jsonl').read_text(encoding='utf-8').splitlines()]
for i, row in enumerate(rows):
    payload = row.get('payload', {})
    messages = payload.get('messages', [])
    if any("Why couldn't you read that file?" in m.get('content', '') for m in messages):
        print(json.dumps({'index': i, 'keys': list(row), 'payload': payload, 'response': row.get('response')}, ensure_ascii=False))
