"""Distinguish first visible text from final-response time in original-model runs."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import statistics

p=argparse.ArgumentParser()
p.add_argument('tag')
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/K2_HORIZON_NATIVE699'/('run-'+a.tag)
raw=Path(os.environ['LOCALAPPDATA'])/f'BAXY/C03-k2-native699-{a.tag}-private/results.jsonl'
rows=[json.loads(line) for line in raw.read_text(encoding='utf-8').splitlines()]
assert len(rows)==50 and (out/'RESOURCES.json').exists()
def stats(key):
    values=[r[key] for r in rows if key in r]
    return dict(count=len(values),median=statistics.median(values) if values else None,
        max=max(values) if values else None)
data=dict(tag=a.tag,results_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
    first_any_token_seconds=stats('first_token_seconds'),first_visible_text_seconds=stats('first_content_seconds'),
    complete_response_seconds=stats('seconds'),
    no_visible_text=[dict(case=r['case'],seconds=r['seconds'],finish_reason=r.get('finish_reason')) for r in rows if not r['content'].strip()],
    scope='Native HTTP stream only, not BAXY display/audio latency. First-any-token can be hidden reasoning. First-visible statistics only include rows with text; absent text is explicitly listed and never treated as a fast success.')
(out/'RESPONSE_TIMING.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(data))
