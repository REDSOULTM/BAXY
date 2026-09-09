import json
import os
from pathlib import Path

base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
def primary(folder):
    return next(r['payload'] for line in (base / folder / 'http-posts.jsonl').open(encoding='utf-8-sig')
                if (r := json.loads(line)).get('stage') == 'request'
                and len(r['payload'].get('tools', [])) == 28
                and r['payload']['messages'][-1].get('content') == 'Me llamo Álvaro.')
a, b = primary('C03-stored-product402b-private'), primary('C03-stored-product404b-private')
result = {'equal_nonmessages': {k: a.get(k) == b.get(k) for k in a.keys() | b.keys() if k != 'messages'},
          'messages402b': a['messages'], 'messages404b': b['messages']}
out = Path(__file__).resolve().parents[1] / 'artifacts/comprobaciones/C03/astra-stored-product404b/payload-diff.json'
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result['equal_nonmessages']))
for label, payload in [('402b', a), ('404b', b)]:
    print(label)
    for message in payload['messages']:
        if message['role'] != 'system':
            print(json.dumps(message, ensure_ascii=True))
