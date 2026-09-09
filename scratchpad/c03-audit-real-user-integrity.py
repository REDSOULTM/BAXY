"""Check literal completeness against source lengths; keep the raw pool immutable."""
from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-real-user-pool-20260906'
trace = root.parent / 'Probando Gemma 4/gemma4_agent/data/traces.jsonl'
observed = {}
with trace.open(encoding='utf-8-sig') as stream:
    for number, line in enumerate(stream, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get('kind') != 'request_start':
            continue
        content = row.get('content', {})
        literal = content.get('text') or content.get('preview')
        if not literal:
            continue
        digest = hashlib.sha256(literal.encode('utf-8')).hexdigest()
        observed.setdefault(digest, []).append({
            'line': number, 'turn_id': row.get('turn_id'),
            'explicit_full_text': bool(content.get('text')),
            'reported_chars': content.get('chars'), 'captured_chars': len(literal),
            'length_matches': content.get('chars') == len(literal),
        })
cases = json.loads((root / 'artifacts/comprobaciones/C03/astra-real-users-development20/CASES.json').read_text(encoding='utf-8'))
selected = {row['id'] for row in cases}
counts = {'total_candidates': 0, 'complete_length_evidence': 0, 'needs_literal_integrity_review': 0,
          'selected_development_cases': len(selected), 'selected_without_complete_length_evidence': 0}
with (private / 'unique_requests.jsonl').open(encoding='utf-8') as stream, (private / 'literal_integrity.jsonl').open('w', encoding='utf-8') as target:
    for line in stream:
        row = json.loads(line)
        evidence = observed.get(row['id'], [])
        complete = any(item['explicit_full_text'] or item['length_matches'] for item in evidence)
        counts['total_candidates'] += 1
        counts['complete_length_evidence' if complete else 'needs_literal_integrity_review'] += 1
        if row['id'] in selected and not complete:
            counts['selected_without_complete_length_evidence'] += 1
        target.write(json.dumps({'id': row['id'], 'complete_length_evidence': complete,
                                 'source_evidence': evidence, 'human_authorship': 'unverified',
                                 'development20': row['id'] in selected}, ensure_ascii=False) + '\n')
summary = {'counts': counts, 'method': 'Match literal SHA256 to live trace content.text or matching content.chars. Length agreement supports complete extraction, not human authorship or freshness. Raw pool unchanged; unresolved candidates are not ready for acceptance.',
           'privateDetails': str(private / 'literal_integrity.jsonl')}
(root / 'artifacts/comprobaciones/C03/REAL_USER_LITERAL_INTEGRITY.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary))
