"""Extend the immutable reserve audit with exact paths from C03 drivers."""
from pathlib import Path
import collections
import hashlib
import json
import os
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-real-user-pool-20260906/reserve-audit-tranche45'
rows = [json.loads(l) for l in (PRIVATE/'review.jsonl').open(encoding='utf-8')]
index = collections.defaultdict(list)
def key(s): return ' '.join(unicodedata.normalize('NFC', s).casefold().split())
for row in rows: index[key(row['text_literal'])].append(row['id'])
names = set()
for path in (ROOT/'scratchpad').glob('c03-*.py'):
    names.update(re.findall(r'\bastra-[a-z0-9-]+', path.read_text(encoding='utf-8-sig')))
found = collections.defaultdict(list)
sources = []

def visit(value, ref):
    if isinstance(value, str):
        for row_id in index.get(key(value), ()):
            if ref not in found[row_id]: found[row_id].append(ref)
    elif isinstance(value, dict):
        for item in value.values(): visit(item, ref)
    elif isinstance(value, list):
        for item in value: visit(item, ref)

for name in sorted(names):
    for filename in ('CASES.json', 'cases.json', 'PREREG.json', 'replies.jsonl'):
        path = ROOT/'artifacts/comprobaciones/C03'/name/filename
        if not path.is_file(): continue
        size = path.stat().st_size
        if path.suffix == '.json' and size > 1_000_000:
            sources.append({'path': str(path), 'bytes': size, 'skipped': 'large_json_requires_targeted_read'})
            continue
        with path.open('rb') as f: digest = hashlib.file_digest(f, 'sha256').hexdigest()
        sources.append({'path': str(path), 'bytes': size, 'sha256': digest})
        with path.open(encoding='utf-8-sig') as f:
            if path.suffix == '.json': visit(json.load(f), f'{name}/{filename}')
            else:
                for number,line in enumerate(f,1): visit(json.loads(line),f'{name}/{filename}:{number}')

not_disproved=[]
with (PRIVATE/'review-with-probes.jsonl').open('x',encoding='utf-8') as f:
    for row in rows:
        refs=found.get(row['id'],[])
        row['probe_or_preregistered_exposure']=refs
        if refs: row['freshness_review']='known_exposure'
        if row['freshness_review'].startswith('not_'):not_disproved.append(row['id'])
        f.write(json.dumps(row,ensure_ascii=False)+'\n')
result={'source_count':len(sources),'probe_or_preregistered_match':len(found),
        'remaining_not_disproved':len(not_disproved),'private_report':str(PRIVATE/'review-with-probes.jsonl'),
        'limits':['Preregistration establishes selection/exposure, not successful execution.',
                  'No inference about human authorship. Unmatched is not accepted.',
                  'No artifact directory traversal; exact filenames derived from inherited drivers.']}
(PRIVATE/'probe-source-manifest.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
(ROOT/'artifacts/comprobaciones/C03/RESERVE_PROBE_EXPOSURE45.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
