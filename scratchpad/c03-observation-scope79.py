from pathlib import Path
import hashlib
import json
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind import effect_intent

sys.stdout.reconfigure(encoding='utf-8')
base = root / 'artifacts/comprobaciones/C03'
stage = sys.argv[1] if len(sys.argv) > 1 else '79'
assert stage in {'79', '80'}
out = base / ('astra-observation-scope' + stage)
out.mkdir(exist_ok=False)
wire = [json.loads(s) for s in (base / 'astra-files77-template/wire-31624.jsonl').read_text(encoding='utf-8').splitlines()]
packet = next(row['payload'] for row in wire if row['payload'].get('tool_choice') == 'auto')
available = [tool['function']['name'].removeprefix('baxy_').replace('__', '.') for tool in packet['tools']]
if stage == '80':
    # The file selector shortlist79 excluded these operations. It cannot
    # reproduce the product's pre-selector grammar and is not a baseline.
    available = ['system.time', 'audio.status', 'system.status']
cases = [
    'Dime la hora, el audio y el uso de CPU.',
    'Dime la hora, revisa el estado del audio y dime el uso de CPU.',
    'Dime la hora y el estado del audio.',
]
(out / 'PREREG.json').write_text(json.dumps({'method': 'Read-only diagnostic of explicit_effects before the LLM. '
    '77/t9 selects only audio.status; inherited52 repeated-verbs control works. No new rules/model calls/effects, '
    'UI/audio/human reserve. Capture actual clause/record state at resolver return and unresolved compound verdict.',
    'sourceSha256': hashlib.sha256((root / 'src/baxy_mind/effect_intent.py').read_bytes()).hexdigest(),
    'availabilityScope': 'Three catalogued observation leaves isolated; not a whole-catalog replay.' if stage == '80' else 'File selector shortlist; invalid availability for reproducing system observations.',
    'cases': cases, 'available': available}, ensure_ascii=False, indent=2), encoding='utf-8')
rows = []
for request in cases:
    capture = {}
    def trace(frame, event, arg):
        if frame.f_code.co_name == 'resolve_explicit_effects' and event == 'return':
            capture.update({k: frame.f_locals.get(k) for k in ('clauses', 'records', 'shared_domain_minimum', 'spoken_report_minimum')})
            capture['return_line'] = frame.f_lineno
        return trace
    sys.settrace(trace)
    try:
        intent = effect_intent.resolve_explicit_effects(request, available)
    finally:
        sys.settrace(None)
    row = {'request': request, 'intent': None if intent is None else {'operations': intent.operations, 'evidence': intent.evidence},
        'resolver': capture,
        'unresolved': repr(effect_intent.unresolved_compound_contract(request, available, resolved_intent=intent))}
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False, default=str))
(out / 'RESULT.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
