"""Produce reviewable native outputs and measurements, without automatic credit."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import statistics

parser = argparse.ArgumentParser()
parser.add_argument('tag')
parser.add_argument('--ablation700', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696'
private = Path(os.environ['LOCALAPPDATA']) / f'BAXY/C03-k2-run696-{args.tag}-private'
panel_path = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-k2-comparison696-private/panel.json'
if args.ablation700:
    base = root/'artifacts/comprobaciones/C03/K2_HORIZON_SELECTOR700'
    private = Path(os.environ['LOCALAPPDATA'])/f'BAXY/C03-k2-ablation700-{args.tag}-private'
    panel_path = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-selector-ablation700-private/panel.json'
panel = json.loads(panel_path.read_text(encoding='utf-8'))
prereg = json.loads((base / ('run-' + args.tag) / 'PREREG.json').read_text(encoding='utf-8'))
panel = [row for row in panel if row['id'] in prereg['cases']]
results_path = private / 'results.jsonl'
results = [json.loads(line) for line in results_path.read_text(encoding='utf-8').splitlines()]
assert len(results) == len(prereg['cases']) and [r['case'] for r in results] == [r['id'] for r in panel] == prereg['cases']
if args.ablation700:
    parity = [json.loads(line) for line in (base/('run-'+args.tag)/'PAYLOAD_PARITY.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(parity) == 20 and all(r['equal_except_removed_system'] for r in parity)
stop_path = base / ('run-' + args.tag) / 'OPERATOR_STOP.json'
operator_stop = None
if stop_path.exists():
    operator_stop = json.loads(stop_path.read_text(encoding='utf-8'))
    completed = operator_stop['completed_before_stop']
    assert completed == [r['case'] for r in results[:len(completed)]]
    assert len(completed) == 20 and all(r['kind'] == 'selector' for r in panel[:20])
    # Preserve all raw requests/results. Only the complete pre-stop category has
    # interpretable quality/latency data; cancellation and refused requests do not.
    panel, results = panel[:20], results[:20]

def tools_in(record):
    calls = {}
    for delta in record['tool_deltas']:
        item = calls.setdefault(delta['index'], {'name': '', 'arguments': ''})
        for key in ['name', 'arguments']:
            item[key] += delta.get('function', {}).get(key, '')
    return list(calls.values())

review = []
for case, result in zip(panel, results, strict=True):
    row = {k: v for k, v in case.items() if k != 'payload'}
    row.update(input=case['payload']['messages'], response={k: v for k, v in result.items() if k != 'reasoning_content'},
               calls=tools_in(result), reasoning_characters=len(result['reasoning_content']), verdict=None)
    review.append(row)
review_path = private / 'review.json'
if review_path.exists():
    existing = json.loads(review_path.read_text(encoding='utf-8'))
    assert [(r['id'], r['response']) for r in existing] == [(r['id'], r['response']) for r in review]
    if any(r.get('verdict') is not None for r in existing):
        review = existing
review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def stats(key):
    values = [r[key] for r in results if key in r]
    return {'count': len(values), 'median': statistics.median(values) if values else None,
            'max': max(values) if values else None, 'sum': sum(values)}

resources = json.loads((base / ('run-' + args.tag) / 'RESOURCES.json').read_text(encoding='utf-8'))
summary = {'tag': args.tag, 'responses': len(results), 'adjudication': 'pending',
    'operator_stop': operator_stop,
    'excluded_after_operator_stop': prereg['cases'][len(results):] if operator_stop else [],
    'results_sha256': hashlib.sha256(results_path.read_bytes()).hexdigest(), 'resources': resources,
    'finish_reasons': {value: sum(str(r.get('finish_reason')) == value for r in results) for value in sorted({str(r.get('finish_reason')) for r in results})},
    'errors': [r['case'] for r in results if r.get('error')],
    'seconds': stats('seconds'), 'first_token_seconds': stats('first_token_seconds'), 'first_content_seconds': stats('first_content_seconds'),
    'completion_tokens': sum(r.get('usage', {}).get('completion_tokens', 0) for r in results),
    'selector_function_name_matches_only': sum([t['name'] for t in tools_in(r)] == c['expected_functions'] for c, r in zip(panel, results, strict=True) if c['kind'] == 'selector'),
    'note': 'Name matching is a diagnostic, not quality credit. Root must judge all full inputs/facts/output, errors, language and authority. Repeated writer521-6/10 are not independent.'}
(base / ('run-' + args.tag) / 'MEASUREMENTS.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
