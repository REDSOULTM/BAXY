"""Read-only verification of exact source occurrences for the reserved pool475."""
from pathlib import Path
from datetime import datetime, timezone
import collections
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
prior = local / 'C03-reserve-language475-private/review.jsonl'
rows = [json.loads(line) for line in prior.open(encoding='utf-8-sig')]
out = local / 'C03-reserve-source477-private'
public = root / 'artifacts/comprobaciones/C03/astra-reserve-source477'
out.mkdir(exist_ok=True)
public.mkdir(exist_ok=True)
assert not (public / 'RESULT.json').exists(), 'do not overwrite a completed audit'

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def resolve(source):
    if source.startswith('probando_gemma4/'):
        return root.parent / 'Probando Gemma 4' / source.split('/', 1)[1]
    if source.startswith('gemma4_local/'):
        return Path.home() / '.gemma4' / source.split('/', 1)[1]
    return Path(source)

sources = {}
targets = collections.defaultdict(set)
for row in rows:
    for occurrence in row['occurrences']:
        path = resolve(occurrence['source'])
        key = str(path.resolve())
        if key not in sources:
            sources[key] = {'path': key, 'exists': path.is_file(), 'expected_sha256': set()}
        sources[key]['expected_sha256'].add(occurrence['source_sha256'])
        location = occurrence['source_location']
        if location.startswith('line:'):
            targets[key].add(int(location.split(':')[1]))

raw = {}
parse_errors = []
for key, source in sources.items():
    source['expected_sha256'] = sorted(source['expected_sha256'])
    if not source['exists']:
        source['hash_matches'] = None
        continue
    path = Path(key)
    source.update(bytes=path.stat().st_size, sha256=sha(path))
    source['hash_matches'] = source['expected_sha256'] == [source['sha256']]
    assert source['hash_matches'], f'changed original source: {key}'
    last_requests = collections.deque(maxlen=2)
    with path.open(encoding='utf-8-sig', errors='strict') as stream:
        for number, line in enumerate(stream, 1):
            if path.suffix == '.jsonl':
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as error:
                    parse_errors.append({'source': key, 'line': number,
                                         'error': str(error), 'target_occurrence': number in targets[key]})
                    continue
                if item.get('kind') != 'request_start':
                    continue
                content = item.get('content') or {}
                text = content.get('text') or content.get('preview') or ''
                event = {'line': number, 'turn_id': item.get('turn_id'),
                         'timestamp': item.get('ts'), 'text': text,
                         'original_char_count': content.get('chars'),
                         'complete_preview': content.get('chars') == len(text)}
            else:
                if 'NUEVA TAREA:' not in line:
                    continue
                text = line.split('NUEVA TAREA:', 1)[1].strip()
                event = {'line': number, 'text': text, 'timestamp': line.split(']', 1)[0] + ']',
                         'log_limit': 100, 'complete_preview': len(text) < 100}
            if number in targets[key]:
                raw[(key, number)] = {**event, 'previous_requests_in_file': list(last_requests)}
            last_requests.append(event)

review = []
for row in rows:
    checks = []
    for occurrence in row['occurrences']:
        key = str(resolve(occurrence['source']).resolve())
        location = occurrence['source_location']
        event = raw.get((key, int(location.split(':')[1]))) if location.startswith('line:') else None
        checks.append({'source': key, 'source_location': location,
                       'source_hash_matches': sources[key]['hash_matches'],
                       'source_event_found': event is not None,
                       'literal_matches': event['text'] == row['text_literal'] if event else None,
                       'complete_preview': event['complete_preview'] if event else None,
                       'event': event})
    verified = any(c['source_hash_matches'] and c['literal_matches'] and c['complete_preview'] for c in checks)
    review.append({'id': row['id'], 'ordinal': row['ordinal'], 'language_semantic': row['language_semantic'],
                   'complete_literal_verified_in_current_original': verified,
                   'checks': checks, 'certified_fresh': False, 'frozen': False, 'replayed': False})

(out / 'review.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in review), encoding='utf-8')
write(out / 'sources.json', list(sources.values()))
write(out / 'parse-errors.json', parse_errors)
missing = [s for s in sources.values() if not s['exists']]
summary = {'utc': datetime.now(timezone.utc).isoformat(),
           'method': 'Verify original file SHA and exact user-event literal/completeness, without BAXY inference. Previous request events are context candidates only: adjacency does not prove one session. Do not execute or use reserve texts for development.',
           'reviewed': len(rows), 'resolved_unique_sources': len(sources),
           'original_sources_hash_verified': sum(s['hash_matches'] is True for s in sources.values()),
           'missing_original_sources': len(missing),
           'complete_literal_verified_in_current_original': sum(r['complete_literal_verified_in_current_original'] for r in review),
           'malformed_original_lines': len(parse_errors),
           'malformed_target_lines': sum(e['target_occurrence'] for e in parse_errors),
           'unverified_ordinals': [r['ordinal'] for r in review if not r['complete_literal_verified_in_current_original']],
           'source_metadata_sha256': sha(out / 'sources.json'), 'private_review_sha256': sha(out / 'review.jsonl'),
           'private': str(out), 'certified_fresh': 0, 'frozen': False, 'executed': 0,
           'log_truncation_evidence': {'path': str(root.parent / 'Carter OS AI/Carter_v1/carter_core.py'),
                                      'lines': [5332, 6178], 'mechanism': 'NUEVA TAREA logs user_input[:100]'},
           'limits': ['Seven .gemma4 session originals absent at current registered root and D:/Perfil/.gemma4; source_manifest retains hashes, not the original dialogue.',
                      'A complete historical literal and owner authorship do not by themselves establish training/campaign freshness.',
                      'Language review, history continuity, duplicate groups, split and exposure audit still constrain selection.',
                      'Do not infer truncated requests from assistant answers. No original files or questionnaire modified.']}
write(public / 'RESULT.json', summary)
print(json.dumps(summary, ensure_ascii=True), flush=True)
