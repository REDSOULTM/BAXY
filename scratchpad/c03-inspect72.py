from pathlib import Path
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

root = Path(__file__).resolve().parents[1]
folder = root / 'artifacts/comprobaciones/C03/astra-files72-qwen35'
paired = json.loads((folder / 'paired.json').read_text(encoding='utf-8'))
for turn in paired:
    print(json.dumps({'turn': turn['turnId'], 'final': turn['final'],
        'progress': [e['label'] for e in turn['publicEvents'] if e.get('type') == 'boot_stage' and e.get('label')]}, ensure_ascii=False))
    if turn['turnId'] in {'t3', 't6', 't7', 't9', 't10'}:
        seen = set()
        for row in turn['compose']:
            if row['intent'] != 'progress' and row.get('draft') not in seen:
                seen.add(row.get('draft'))
                print(json.dumps({k: row.get(k) for k in ('trace', 'stage', 'intent', 'reason', 'payload', 'draft')}, ensure_ascii=False))
