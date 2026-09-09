"""Bounded read of every final and its observation; no adjudication inferred."""
from pathlib import Path
import json
import os

private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-window-facts-product661-private'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
panel = read(private / 'panel.json')
finals = []
with (private / 'capture/events.jsonl').open(encoding='utf-8-sig') as stream:
    for line in stream:
        row = json.loads(line)
        if row.get('type') == 'terminal':
            finals.append(row)
observations = {}
with (private / 'compose-audit.jsonl').open(encoding='utf-8-sig') as stream:
    for line in stream:
        row = json.loads(line)
        if row.get('published') and row.get('payload', {}).get('operation'):
            observations[row['trace']] = row['payload']
assert len(panel) == len(finals) == 24
for i, (case, final) in enumerate(zip(panel, finals), 1):
    print(json.dumps({'turn': i, 'case': case, 'final': final,
                      'observation': observations.get(f't{i}')}, ensure_ascii=False))
for name in ['before', 'after']:
    snapshot = read(private / f'windows-{name}.json')
    print(json.dumps({'snapshot': name, 'foreground': snapshot['foreground'],
                      'windows': [{k: row.get(k) for k in ['process', 'title', 'aumid', 'identity_error']}
                                  for row in snapshot['windows']]}, ensure_ascii=False))
