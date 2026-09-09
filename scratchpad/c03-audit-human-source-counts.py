import collections
import json
import os
from pathlib import Path

pool = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-real-user-pool-20260906/unique_requests.jsonl'
counts = collections.Counter()
sessions = {}
with pool.open(encoding='utf-8') as stream:
    for line in stream:
        row = json.loads(line)
        for source in {str(o['source']) for o in row['occurrences']}:
            counts[source] += 1
            if '/sessions/' in source.replace('\\', '/'):
                sessions.setdefault(source, []).append({'id': row['id'], 'text_literal': row['text_literal'], 'occurrences': [o for o in row['occurrences'] if o['source'] == source]})
out = pool.with_name('session_source_candidates.json')
out.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'unique_by_source': counts.most_common(15), 'session_source_count': len(sessions), 'private_detail': str(out)}, ensure_ascii=False))
