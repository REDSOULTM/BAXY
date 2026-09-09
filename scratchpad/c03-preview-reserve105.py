from pathlib import Path
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

source = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-real-user-pool-20260906/reserve-audit-tranche45/review-with-probes.jsonl'
rows = [json.loads(line) for line in source.open(encoding='utf-8')]
eligible = [r for r in rows if r['freshness_review'].startswith('not_')]
for index, row in enumerate(eligible):
    first = row['occurrences'][0]
    print(json.dumps({'n': index, 'id': row['id'][:12], 'text': row['text_literal'],
        'source': first.get('source'), 'time': first.get('timestamp'),
        'location': first.get('source_location')}, ensure_ascii=False))
