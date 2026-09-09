"""Read-only audit of literal provenance/exposure; never run candidate requests."""
from pathlib import Path
import ast
import collections
import datetime
import hashlib
import json
import os
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-real-user-pool-20260906'
OUT = PRIVATE / 'reserve-audit-tranche45'
OUT.mkdir(exist_ok=False)

def key(text):
    return ' '.join(unicodedata.normalize('NFC', text).casefold().split())

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

pool = [json.loads(line) for line in (PRIVATE / 'unique_requests.jsonl').open(encoding='utf-8')]
by_key = collections.defaultdict(list)
for row in pool:
    by_key[key(row['text_literal'])].append(row)
exposures = {r['id']: collections.defaultdict(list) for r in pool}
sources = []

def record(text, category, reference):
    for row in by_key.get(key(text), []):
        if reference not in exposures[row['id']][category]:
            exposures[row['id']][category].append(reference)

historical = ROOT / 'tests/data/historical_messages.jsonl'
sources.append({'path': str(historical), 'sha256': sha(historical), 'method': 'stream; exact casefold NFC whitespace match, no accent/punctuation removal'})
for number, line in enumerate(historical.open(encoding='utf-8-sig'), 1):
    row = json.loads(line)
    record(row.get('text_literal', ''), 'historical_' + str(row.get('origin')), {
        'line': number, 'source': row.get('source'), 'location': row.get('source_location'),
        'message_id': row.get('message_id'), 'source_sha256': row.get('source_sha256'),
    })

runtime = ROOT / 'tests/data/turn_evidence_runtime.v1.jsonl'
sources.append({'path': str(runtime), 'sha256': sha(runtime), 'method': 'registered retrieval examples; not a claim about Qwen pretraining'})
for number, line in enumerate(runtime.open(encoding='utf-8-sig'), 1):
    row = json.loads(line)
    record(row.get('text', ''), 'runtime_retrieval', {'line': number, 'source_id': row.get('source_id'), 'split': row.get('split')})

# Locate output names in the inherited drivers, then open only exact paths.
# Never walk artifacts; absent probes or raw LLM panels are not silently
# treated as untouched: this category measures product replay only.
names = set()
drivers = sorted((ROOT / 'scratchpad').glob('c03-*.py'))
for path in drivers:
    names.update(re.findall(r'\bastra-[a-z0-9-]+', path.read_text(encoding='utf-8-sig')))
for name in sorted(names):
    path = ROOT / 'artifacts/comprobaciones/C03' / (name + '.turns.jsonl')
    if not path.is_file():
        continue
    folder = path.parent / name
    if not (folder / 'PREREG.json').is_file():
        continue
    sources.append({'path': str(path), 'sha256': sha(path), 'method': 'product replay input; existence of prereg, completion not implied'})
    for number, line in enumerate(path.open(encoding='utf-8-sig'), 1):
        row = json.loads(line)
        if row.get('cmd') == 'turn':
            record(row.get('text', ''), 'c03_product_exposed', {'panel': name, 'line': number})

code_paths = set((ROOT / 'tests').glob('test_*.py'))
code_paths.update(drivers)
legacy = ROOT.parent / 'Carter OS AI/Carter_v1'
code_paths.update(legacy.glob('*.py'))
code_paths.update((legacy / 'tests').glob('*.py'))
for path in sorted(code_paths):
    try:
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    except (SyntaxError, UnicodeError):
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            record(node.value, 'code_literal_exposed', {'path': str(path), 'line': node.lineno})

counts = collections.Counter()
possible = []
with (OUT / 'review.jsonl').open('w', encoding='utf-8') as f:
    for row in pool:
        e = dict(exposures[row['id']])
        for category in e:
            counts[category] += 1
        already_exposed = any(c in e for c in ('c03_product_exposed', 'runtime_retrieval', 'code_literal_exposed'))
        item = {**row, 'exposure_evidence': e, 'freshness_review': 'known_exposure' if already_exposed else 'not_disproved_by_this_audit', 'human_authorship': 'not_certified_by_exposure_audit'}
        f.write(json.dumps(item, ensure_ascii=False) + '\n')
        if not already_exposed:
            possible.append(row['id'])
summary = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'pool_total': len(pool), 'counts': dict(counts), 'not_disproved': len(possible), 'private_report': str(OUT / 'review.jsonl'), 'sources': sources,
           'limits': ['No executions; no acceptance set frozen.', 'An unexposed text is not automatically human-authored or fresh.', 'Casefold/NFC/whitespace joins preserve original literals; punctuation remains distinct.', 'Raw model probes, prior LoRA data and historical benchmark sources still need review before acceptance.', 'Code overlap establishes exposure, not whether the human or the test authored the text first.']}
(OUT / 'MANIFEST.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
public = {k: v for k, v in summary.items() if k != 'sources'}
public['source_manifest'] = str(OUT / 'MANIFEST.json')
(ROOT / 'artifacts/comprobaciones/C03/RESERVE_PROVENANCE_AUDIT45.json').write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(public, ensure_ascii=False))
