"""Correlate frozen809 outputs; no verdict inferred from terminal status."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re

parser = argparse.ArgumentParser()
parser.add_argument('--partial', action='store_true')
parser.add_argument('--start', type=int, default=0)
parser.add_argument('--count', type=int, default=25)
parser.add_argument('--summary', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-process-batch809-private'
public = root / 'artifacts/comprobaciones/C03/PROCESS_BATCH809'
truncated = []


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def rows(path):
    if not path.exists() and args.partial:
        return []
    result = []
    lines = path.read_bytes().decode('utf-8-sig').splitlines(keepends=True)
    for index, line in enumerate(lines):
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            if not (args.partial and index == len(lines) - 1 and not line.endswith('\n')):
                raise
            truncated.append(path.name)
    return result


panel = read(private / 'panel.json')
assert len(panel) == 50
prereg = read(public / 'PREREG.json')
full_path = Path(prereg['full_validation_path'])
assert hashlib.sha256(full_path.read_bytes()).hexdigest() == prereg['full_validation_sha256']
assert read(full_path)['exit_code'] == 0 and read(full_path)['source_pins_unchanged'] is True
baseline_pins_path = Path(prereg['full_baseline_source_pins_path'])
assert baseline_pins_path == root / 'artifacts/comprobaciones/C03/PROCESS_DEADLINE804/SOURCE_PINS.json'
assert full_path == baseline_pins_path.parent / 'FULL_RETRY1/FULL_EXIT.json'
baseline_pins_sha = hashlib.sha256(baseline_pins_path.read_bytes()).hexdigest()
assert baseline_pins_sha == prereg['full_baseline_source_pins_sha256']
assert baseline_pins_sha == read(full_path)['source_pins_sha256']
validation_root = root / 'artifacts/comprobaciones/C03/PROCESS_ROWS808'
for path_key, sha_key, filename in [
    ('validation_path', 'validation_sha256', 'VALIDATION_EXIT.json'),
    ('owners_python_path', 'owners_python_sha256', 'OWNERS_PYTHON_EXIT.json'),
]:
    validation_path = Path(prereg[path_key])
    assert validation_path == validation_root / filename
    assert hashlib.sha256(validation_path.read_bytes()).hexdigest() == prereg[sha_key]
    assert read(validation_path)['exit_code'] == 0
scope_pins_path = validation_root / 'SOURCE_PINS.json'
assert hashlib.sha256(scope_pins_path.read_bytes()).hexdigest() == prereg['source808_pins_sha256']
assert read(scope_pins_path) == prereg['source808_pins']
assert len(prereg['source808_pins']) == 29
assert read(validation_root / 'VALIDATION_EXIT.json')['source_pins_unchanged'] is True
assert read(validation_root / 'VALIDATION_EXIT.json')['source_pins_sha256'] == prereg['source808_pins_sha256']
assert hashlib.sha256((private / 'panel.json').read_bytes()).hexdigest() == prereg['panel_sha256']
assert [{'case_id': c['case_id'], 'group': c['group']} for c in panel] == prereg['cases']
if not args.partial:
    outcome = read(public / 'EXIT.json')
    assert outcome['exit_code'] == 0, outcome
    assert all(outcome[k] for k in ['manifest_unchanged', 'sources_unchanged',
                                  'source808_unchanged', 'runner_unchanged', 'app_dll_unchanged'])
finals = [r for r in rows(private / 'capture/events.jsonl') if r.get('type') == 'terminal']
assert len(finals) <= len(panel)
if not args.partial:
    assert len(finals) == len(panel)
shell = rows(private / 'shell-trace.jsonl')
compose = rows(private / 'compose-audit.jsonl')
decisions = {r['request_id']: r for r in rows(private / 'turn-audit.jsonl') if r.get('phase') == 'final'}
review = []
for index, (case, final) in enumerate(zip(panel, finals), 1):
    trace = [r for r in shell if r['scope'] == 'turn' and r['id'] == f't{index}']
    ids = [m[1] for r in trace if (m := re.search(r'turn\.decide\.id\.(\d+)\.', r.get('detail') or ''))]
    drafts = [r for r in compose if r.get('trace') == f't{index}']
    review.append({**case, 'turn_id': f't{index}', 'terminal': final,
                   'core_calls': [r['detail'] for r in trace if r['stage'] == 'core.call.start'],
                   'decisions': [decisions[k] for k in ids if k in decisions], 'compose': drafts,
                   'trace_duration_ms': trace[-1]['ms'] - trace[0]['ms'] if trace else None})
destination = private / ('live-review.json' if args.partial else 'review.json')
destination.write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
summary = {'completed_terminals': len(review), 'registered_total': len(panel), 'partial': args.partial,
           'truncated_tails': truncated, 'quality_adjudicated': False}
if not args.partial:
    (public / 'REVIEW_CAPTURE.json').write_bytes((json.dumps(summary, indent=2) + '\n').encode('utf-8'))
    markdown = ['# Respuestas privadas809 — pendientes de adjudicación',
                'Entradas y criterios congelados; diagnóstico del producto registrado.\n']
    for r in review:
        markdown.extend([f"## {r['turn_id']} · {r['case_id']} · {r['group']}",
                         f"**Entrada:** {r['text']}", f"**Criterio:** {r['criterion']}",
                         f"**Respuesta:** {r['terminal']['final']}",
                         '```json\n' + json.dumps({'decisions': r['decisions'], 'compose': r['compose']},
                                                   ensure_ascii=False, indent=2) + '\n```'])
    (private / 'RESPUESTAS.md').write_text('\n\n'.join(markdown) + '\n', encoding='utf-8')
print(json.dumps(summary))
for r in review[args.start:args.start + args.count]:
    first = next((d for d in r['compose'] if d.get('stage') == 'first'
                  and isinstance(d.get('payload'), dict)
                  and ('operation' in d['payload'] or 'completedStepsInOrder' in d['payload'])), {})
    print(json.dumps({'id': r['case_id'], 'turn': r['turn_id'], 'group': r['group'], 'text': r['text'],
                      'final': r['terminal']['final'], 'kind': r['terminal']['kind'],
                      'core_calls': r['core_calls'], 'milliseconds': r['trace_duration_ms'],
                      'facts': None if args.summary else first.get('payload'),
                      'rejected': None if args.summary else [
                          {k: d.get(k) for k in ['stage', 'draft', 'reason']} for d in r['compose'] if d.get('reason')]},
                     ensure_ascii=False))
