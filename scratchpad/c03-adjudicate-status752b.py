"""Seal manual752B adjudication against its own fresh facts and frozen criteria."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import statistics

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/STATUS_BATCH752B'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-status-batch752b-private'
read = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
rows = read(private / 'review.json')
exit_record = read(out / 'EXIT.json')
assert exit_record['exit_code'] == 0 and len(rows) == 73
assert all(exit_record[k] for k in ['manifest_unchanged', 'sources_unchanged', 'source751_unchanged',
                                   'runner_unchanged', 'app_dll_unchanged'])
assert not (out / 'RESULT.json').exists()
failures = {}


def fail(ids, category, reason):
    for key in ids.split():
        assert key not in failures
        failures[key] = {'category': category, 'reason': reason}


fail('H0023 H0103', 'inventory_composition_not_delivered',
     'window.resolve reached Core, but no final inventory composition was captured or delivered. '
     'The captured status text is not the requested inventory. The internal cause remains unproved.')
fail('H0209 H0663 windows-all-en', 'global_inventory_interpretation',
     'No inventory read reached Core. Spanish raw proposals for window.resolve were vetoed by domain_grounding; '
     'the English raw proposal selected window.active, then was vetoed. The global parser misses these envelopes; '
     'clarification does not fulfill the request, and the English final is also Spanish.')
fail('windows-focus-mixed', 'faithful_focus_draft_rejected',
     'Fresh foreground data identifies ChatGPT. Eighteen drafts identify that focus correctly using ventanal/focus, '
     'but window prose validation rejects them as missing_fact and no final is delivered.')
fail('H0532 H0675', 'no_fresh_read',
     'Current RAM capacity/process ranking is answered from conversational history without a fresh requested read. '
     'The final plausible value does not establish the current machine observation or aggregate app memory.')
fail('H0539 H0655 H0508', 'memory_total_labelled_available',
     'Fresh total usable RAM is labelled available; actual available RAM is a different, much smaller field. '
     'The requested capacity is not distinguished from free memory.')
fail('H0359 H0450 H0499 H0602 clock-date-en audio-order-es', 'supported_read_not_selected',
     'The supported battery/time/date/audio read did not reach Core. Interpretation failure, unsupported prose '
     'or composition_failed does not fulfill the requested observation.')
fail('H0732', 'internet_not_observed',
     'network.status online is derived from interfaces with OperationalStatus.Up, not verified Internet reachability. '
     'The provider source confirms that limitation; the user asked for Internet.')
fail('network-wifi-en', 'wifi_scope_expanded',
     'The WLAN observation supports no Wi-Fi connection, while the final claims no network connection of any kind.')
fail('network-internet-es', 'supported_read_not_selected',
     'No network operation ran; the final denies the requested capability. No connectivity observation was obtained.')
fail('H0364 processes-top2-es', 'cpu_process_metric_and_membership',
     'The provider sorts lifetime TotalProcessorSeconds, not current CPU consumption. The prose also drops distinct '
     'same-name processes and promotes different members as if they were the requested ranking.')
fail('H0114 H0650', 'numeric_precision_not_accredited',
     'Requested facts/ranking are substantially present, but some displayed values truncate instead of rounding '
     'at the shown precision. Conservatively not accredited; counted separately as two precision-sensitive cases, '
     'not as loss of capability or evidence that source750/751 regressed. Exact values are in the private review.')
assert len(failures) == 24 and set(failures) <= {r['case_id'] for r in rows}
passed = {
    'windows': 'Fresh foreground observation supports the named focused window and any stated display state.',
    'disk': 'Fresh disk observation supports the requested free/used amount with matching decimal units and requested drive.',
    'gpu': 'Fresh single/plan GPU observations support the reported adapter, capacity or usage without claiming unobserved adapters.',
    'memory': 'Fresh memory observation supports the requested installed, free or used amount with matching label and units.',
    'battery': 'Fresh battery observation supports the reported percentage, charging and AC state.',
    'cpu': 'The final gives the freshly measured CPU usage percentage; rejected drafts are retained separately.',
    'clock': 'A fresh system.time read supports the requested local time/date and language.',
    'network': 'Fresh WLAN observation supports the narrowly worded absence of Wi-Fi connection.',
    'processes': 'Fresh memory-sorted inventory supports the requested three process entries and exact byte values.',
    'audio': 'Fresh default output endpoint observation supports the reported volume and mute state; no volume effect ran.',
}
verdicts = []
for row in rows:
    failure = failures.get(row['case_id'])
    if failure is None:
        assert row['terminal']['kind'] == 'published_final' and row['core_calls']
    verdicts.append({'case_id': row['case_id'], 'group': row['group'], 'turn_id': row['turn_id'],
                     'correct': failure is None, **(failure or {'category': 'verified_answer', 'reason': passed[row['group']]})})
durations = [r['trace_duration_ms'] / 1000 for r in rows]
result = {
    'utc': datetime.now(timezone.utc).isoformat(), 'status': 'diagnostic_adjudicated',
    'cases': 73, 'correct': 49, 'not_accredited': 24, 'substantive_failures': 22,
    'precision_sensitive': 2, 'coverage_added': 0,
    'survey': {'covered': 26, 'open': 716, 'not_applicable': 0},
    'method': 'All73 finals, current facts, criteria, failure decisions and rejected drafts were read by root. '
              'Same frozen panel as689/729, current registered product. Not a native model comparison, blind test, '
              'UI/voice acceptance or causal score comparison across changing PC state.',
    'precision_sensitivity': 'Accepting displayed truncation in H0114/H0650 gives51/73 instead of49/73. '
                             'This diagnostic keeps both unaccredited and does not introduce a new product threshold.',
    'failure_categories': dict(Counter(v['category'] for v in verdicts if not v['correct'])),
    'latency_seconds': {'scope': 'first to last turn trace, including recovery; not UI/voice time',
                        'median': statistics.median(durations), 'maximum': max(durations)},
    'resources': read(out / 'RESOURCES.json'), 'panel_sha256': sha(private / 'panel.json'),
    'evidence_sha256': {name: sha(private / name) for name in [
        'panel.json', 'review.json', 'capture/events.jsonl', 'shell-trace.jsonl', 'turn-audit.jsonl',
        'compose-audit.jsonl', 'raw-replies.jsonl', 'processes.json', 'memory-samples.jsonl']},
    'verdicts': verdicts,
}
(out / 'RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(private / 'adjudication.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
markdown = ['# Adjudicación privada752B', '49 acreditadas;22 fallos sustantivos;2 casos de precisión no acreditados. '
            'No añade cobertura de encuesta. Payloads y borradores completos: RESPUESTAS.md y review.json.']
for row, verdict in zip(rows, verdicts):
    markdown.extend([f"## {row['turn_id']} · {row['case_id']} · {'correcto' if verdict['correct'] else 'no acreditado'}",
                     '**Entrada:** ' + row['text'], '**Respuesta:** ' + row['terminal']['final'],
                     '**Criterio:** ' + row['criterion'], '**Adjudicación:** ' + verdict['reason'],
                     '**Operaciones:** ' + json.dumps(row['core_calls'])])
(private / 'ADJUDICACION.md').write_text('\n\n'.join(markdown) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in {'verdicts', 'evidence_sha256'}}, ensure_ascii=False))
