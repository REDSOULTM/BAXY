import json
import sys

# Prints the YOU/BAXY dialogue of a conductor capture's events.jsonl.
for line in open(sys.argv[1], encoding='utf-8-sig'):
    if not line.strip():
        continue
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        continue
    inner = event.get('event') or {}
    if inner.get('type') == 'activity':
        entry = inner.get('entry') or {}
        sys.stdout.buffer.write(f"{entry.get('ts')} {entry.get('src')} | {str(entry.get('msg'))[:220]}\n".encode('utf-8'))
