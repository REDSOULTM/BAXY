from pathlib import Path
import json
import os

root = Path(__file__).resolve().parents[1]
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
text = 'Which Windows account is running BAXY?'
def first(folder):
    for line in (local / folder / 'http-posts.jsonl').open(encoding='utf-8-sig'):
        row = json.loads(line)
        if (row.get('stage') == 'request' and len(row['payload'].get('tools', [])) == 28
            and row['payload']['messages'][-1].get('content') == text):
            return row['payload']
    raise ValueError(folder)
a = first('C03-account-product411-private')
b = first('C03-read-recovery412-private')
result = {'outside_messages': {k: a.get(k) == b.get(k) for k in a.keys() | b.keys() if k != 'messages'},
          'systems_equal': [m for m in a['messages'] if m['role'] == 'system'] == [m for m in b['messages'] if m['role'] == 'system'],
          'messages411': a['messages'], 'messages412': b['messages']}
target = local / 'C03-read-recovery412-private/payload-diff411.json'
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if not k.startswith('messages')}, ensure_ascii=False))
for label, payload in [('411', a), ('412', b)]:
    print(label)
    for message in payload['messages']:
        if message['role'] != 'system':
            safe = dict(message)
            safe['content'] = safe['content'].replace(os.environ['USERNAME'], '[WINDOWS_IDENTITY]')
            print(json.dumps(safe, ensure_ascii=True))
