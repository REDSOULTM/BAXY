from pathlib import Path
import json
import os

local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private = local / 'C03-read-recovery413-private'
reference = json.loads((local / 'C03-read-recovery413-cases-private/reference411.json').read_text(encoding='utf-8'))
rows = [json.loads(s) for s in (private / 'http-posts.jsonl').open(encoding='utf-8')]
responses = {(r['pid'], r['id']): r for r in rows if r['stage'] == 'response'}
selected = []
for row in rows:
    if row['stage'] != 'request' or row['payload'].get('messages') != reference['messages']:
        continue
    tools = row['payload'].get('tools', [])
    response = responses[(row['pid'], row['id'])]['response']['choices'][0]
    data = {'pid': row['pid'], 'id': row['id'], 'tool_count': len(tools),
            'first4': [t['function']['name'] for t in tools[:4]], 'choice': response}
    selected.append(data)
    safe = dict(data)
    safe['choice'] = json.loads(json.dumps(response).replace(os.environ['USERNAME'], '[WINDOWS_IDENTITY]'))
    print(json.dumps(safe, ensure_ascii=True))
(private / 'actual-target-native-sequence.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
