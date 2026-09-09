"""Extend prior exposure evidence without executing or freezing any pool case."""
from pathlib import Path
import ast
import collections
import hashlib
import json
import os
import re
import subprocess
import unicodedata

root = Path(__file__).resolve().parents[1]
base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
prior = base / 'C03-real-user-pool-20260906/reserve-audit-tranche45/review-with-probes.jsonl'
review = base / 'C03-owner-review328-private/reviewed-records.jsonl'
rows = [json.loads(line) for line in prior.read_text(encoding='utf-8-sig').splitlines()]
owners = {r['id']: r['ownerReview'] for r in map(json.loads, review.read_text(encoding='utf-8-sig').splitlines())}
out = base / 'C03-exposure335-private'
out.mkdir(exist_ok=False)
index = collections.defaultdict(list)

def key(value):
    return ' '.join(unicodedata.normalize('NFC', value).casefold().split())

for row in rows:
    index[key(row['text_literal'])].append(row['id'])
matches = collections.defaultdict(set)
sources = []

def visit(value, reference):
    if isinstance(value, str):
        for identifier in index.get(key(value), []):
            matches[identifier].add(reference)
        # Actual tool payloads sometimes serialize request/history inside a
        # message. Decode only complete JSON, never execute its contents.
        if value.lstrip().startswith(('{', '[')):
            try:
                parsed = json.loads(value)
            except (ValueError, RecursionError):
                return
            if isinstance(parsed, (dict, list)):
                visit(parsed, reference)
    elif isinstance(value, dict):
        for item in value.values():
            visit(item, reference)
    elif isinstance(value, list):
        for item in value:
            visit(item, reference)

def stamp(path, method):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    sources.append({'path': str(path), 'bytes': path.stat().st_size,
                    'sha256': digest, 'method': method})

drivers = sorted((root/'scratchpad').glob('c03-*.py'))
names = set()
for driver in drivers:
    names.update(re.findall(r'\bastra-[a-z0-9-]+', driver.read_text(encoding='utf-8-sig')))

tracked = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard',
                                  '--', 'src', 'tests', 'scripts'], cwd=root).decode('utf-8').split('\0')
paths = {root / name for name in tracked if name.endswith(('.py', '.cs', '.json', '.jsonl'))}
paths.update(drivers)
for path in sorted(paths):
    if not path.is_file():
        continue
    # Corpus files are inherited from45; only the actual retrieval corpus is
    # exposure here. Other data need their separately documented split audit.
    if path.suffix in {'.json', '.jsonl'}:
        if path != root/'tests/data/turn_evidence_runtime.v1.jsonl':
            continue
        stamp(path, 'current runtime retrieval')
        for number, line in enumerate(path.open(encoding='utf-8-sig'), 1):
            visit(json.loads(line), f'{path}:{number}')
        continue
    text = path.read_text(encoding='utf-8-sig')
    stamp(path, 'literal in current source/test/driver; execution not implied')
    if path.suffix == '.py':
        try:
            tree = ast.parse(text)
        except SyntaxError:
            sources[-1]['unparsed'] = True
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                visit(node.value, f'{path}:{node.lineno}')
    else:
        # Plain C# literals only; interpolated/raw/multiline literals remain a
        # declared audit limitation, not an automatic freshness pass.
        for match in re.finditer(r'(?<![$@])"(?:[^"\\\r\n]|\\.)*"', text):
            try:
                value = json.loads(match.group())
            except ValueError:
                continue
            visit(value, f'{path}:{text.count(chr(10), 0, match.start())+1}')

for name in sorted(names):
    for filename in ('CASES.json', 'cases.json', 'PREREG.json', 'replies.jsonl'):
        path = root/'artifacts/comprobaciones/C03'/name/filename
        if not path.is_file():
            continue
        stamp(path, 'exact panel path derived from inherited driver; selection/exposure')
        if path.suffix == '.json' and path.stat().st_size > 1_000_000:
            sources[-1]['unparsed'] = 'large_json_requires_targeted_read'
            continue
        if path.suffix == '.json':
            visit(json.loads(path.read_text(encoding='utf-8-sig')), str(path))
        else:
            for number, line in enumerate(path.open(encoding='utf-8-sig'), 1):
                visit(json.loads(line), f'{path}:{number}')
    turns = root/'artifacts/comprobaciones/C03'/(name+'.turns.jsonl')
    if turns.is_file():
        stamp(turns, 'product request file located by driver name; selection/exposure')
        for number, line in enumerate(turns.open(encoding='utf-8-sig'), 1):
            visit(json.loads(line), f'{turns}:{number}')

remaining = []
newly_exposed = []
with (out/'review.jsonl').open('x', encoding='utf-8') as stream:
    for row in rows:
        row['ownerReview'] = owners[row['id']]
        row['current_exposure335'] = sorted(matches.get(row['id'], []))
        if row['current_exposure335']:
            if row['freshness_review'] != 'known_exposure':
                newly_exposed.append(row['id'])
            row['freshness_review'] = 'known_exposure'
        if row['freshness_review'] != 'known_exposure' and owners[row['id']]['authorship'] is True and owners[row['id']]['capability'] is True:
            remaining.append(row['id'])
        stream.write(json.dumps(row, ensure_ascii=False)+'\n')
(out/'sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(out/'remaining-ids.json').write_text(json.dumps(remaining,indent=2)+'\n',encoding='utf-8')
summary = dict(joined=len(rows), source_count=len(sources), matched_current=len(matches),
    newly_exposed_since45=len(newly_exposed), both_positive_still_requires_audit=len(remaining),
    certified_fresh=0, frozen=False, private_directory=str(out),
    limitations=['Exact literal/NFC/casefold/whitespace only; paraphrases not checked.',
        'No claim about all historical training, split metadata, dynamically composed code, or private HTTP logs.',
        'C# extraction excludes interpolated/verbatim/raw strings; larger JSON recorded unparsed.',
        'Language and original multi-turn context still need semantic adjudication. No case executed.',
        'No artifacts directory traversal: exact names from driver references.'])
public = root/'artifacts/comprobaciones/C03/astra-exposure335'
public.mkdir(exist_ok=False)
(public/'RESULT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True),flush=True)
