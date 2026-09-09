import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private = local / 'C03-os-product417-private'
read = lambda p: [json.loads(line) for line in p.open(encoding='utf-8-sig')]
events = read(private / 'capture/events.jsonl')
journal = [r['payload'] for r in read(local / 'C03-os-profile417/journal/missions.jsonl')]
identities = [(r.get('response') or {}).get('result', {}) for r in journal if r['operation'] == 'system.identity']
names = {v for row in identities if isinstance(row, dict) for v in row.values() if isinstance(v, str) and v}
turns = []
for e in events:
    entry = e.get('event', {}).get('entry', {})
    if entry.get('src') == 'YOU':
        turns.append({'request':entry['msg'], 'answers':[]})
    elif entry.get('src') == 'BAXY' and turns:
        turns[-1]['answers'].append({'text':entry['msg'], 'route':entry.get('route')})
raw = {'turns':turns, 'terminal': [e for e in events if e.get('type') == 'terminal'],
       'reads': [{'operation':r['operation'], 'response':r['response']} for r in journal if (r.get('response') or {}).get('verified')]}
(private / 'adjudication-input.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
text = json.dumps(raw, ensure_ascii=False)
for name in sorted(names, key=len, reverse=True):
    text = text.replace(name, '[WINDOWS_IDENTITY]')
print(text)
