"""Private sealed app-panel correlation only; root owns all quality judgments."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNNER = ROOT / 'scratchpad/c03-application-category-next.py'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def rows(path, partial, truncated):
    if not path.exists() and partial:
        return []
    result = []
    lines = path.read_text(encoding='utf-8-sig').splitlines(keepends=True)
    for index, line in enumerate(lines):
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            if partial and index == len(lines) - 1 and not line.endswith('\n'):
                truncated.append(str(path))
            else:
                raise
    return result


def completed_turns(events):
    """Conductor writes admission, public events, terminal, posterior per turn."""
    completed, pending = [], None
    for event in events:
        if event.get('type') == 'admission':
            require(event.get('command') == 'turn', 'Unexpected command in sealed turn-only panel')
            require(pending is None, 'Admission without previous terminal')
            pending = [event]
        elif event.get('type') == 'terminal':
            require(pending is not None, 'Unattributed terminal (for example runtime startup failure)')
            pending.append(event)
            completed.append(pending)
            pending = None
        elif pending is not None:
            pending.append(event)
    return completed


def correlate(panel, events, shell, compose, decisions, raw):
    blocks = completed_turns(events)
    require(len(blocks) <= len(panel), 'More finals than registered cases')
    result = []
    for ordinal, (case, block) in enumerate(zip(panel, blocks), 1):
        turn = f't{ordinal}'
        trace = [row for row in shell if row.get('scope') == 'turn' and row.get('id') == turn]
        request_ids = {match[1] for row in trace
                       if (match := re.search(r'turn\.decide\.id\.(\d+)\.', str(row.get('detail') or '')))}
        result.append({**case, 'turn_id': turn, 'terminal': block[-1], 'conductor_events': block,
                       'shell_trace': trace,
                       'decisions': [row for row in decisions if str(row.get('request_id')) in request_ids],
                       'compose': [row for row in compose if row.get('trace') == turn],
                       'raw_replies': [row for row in raw if str(row.get('request_id')) in request_ids],
                       'correlation': 'Sealed turn-only command order; admission/terminal pairing checked.',
                       'independent_windows': {
                           'association': 'unavailable',
                           'reason': 'Conductor terminals have no absolute timestamp; shell ms has no verified UTC epoch. Timeline UTC/monotonic values cannot provide reliable per-case brackets.',
                           'sample_indices': []},
                       'root_judgment': 'pending', 'quality_adjudicated': False})
    return result


def associate_samples(panel, shell, samples):
    """Validate producer bookends against actual trace sequence, never UTC guesses."""
    mapping = {case['case_id']: [] for case in panel}
    audit = []
    for index, sample in enumerate(samples):
        association = sample.get('association') if isinstance(sample, dict) else None
        reason = None
        if association is None:
            reason = 'No bookends; legacy or intentionally unassociated sample'
        elif not isinstance(association, dict):
            reason = 'Association must be an object or null'
        else:
            before, after = association.get('seq_before'), association.get('seq_after')
            turn = association.get('turn_id')
            match = re.fullmatch(r't([1-9][0-9]*)', turn) if isinstance(turn, str) else None
            ordinal = int(match[1]) if match else 0
            if association.get('method') != 'trace_bookends':
                reason = 'Unsupported association method'
            elif type(before) is not int or type(after) is not int or not (0 < before <= after):
                reason = 'Invalid bookend sequence bounds'
            elif association.get('core_completed_before') is not True:
                reason = 'No completed core call asserted before observation'
            elif not 1 <= ordinal <= len(panel) or association.get('case_id') != panel[ordinal - 1]['case_id']:
                reason = 'Turn/case mapping differs from sealed panel'
            elif after > len(shell):
                reason = 'Bookend not present in captured trace yet'
            else:
                prefix = shell[:after]
                if any(type(row.get('seq')) is not int or row['seq'] != seq
                       for seq, row in enumerate(prefix, 1)):
                    reason = 'Trace sequence missing, duplicated, reordered or not starting at1'
                elif any(row.get('stage') == 'trace.truncated' for row in prefix):
                    reason = 'Trace truncated before bookends'
                else:
                    starts = [row for row in prefix if row.get('scope') == 'turn'
                              and row.get('stage') == 'queue.wait.end']
                    earlier = [row for row in starts if row['seq'] <= before]
                    if not earlier or not starts or earlier[-1]['id'] != turn or starts[-1]['id'] != turn:
                        reason = 'Last started turn differs across bookends'
                    elif [row.get('id') for row in starts] != [f't{i}' for i in range(1, ordinal + 1)]:
                        reason = 'Turn start sequence differs from sealed command order'
                    elif not any(row.get('scope') == 'turn' and row.get('id') == turn
                                 and row.get('stage') == 'core.call.end'
                                 and earlier[-1]['seq'] < row['seq'] <= before for row in prefix):
                        reason = 'No actual core.call.end before first bookend'
        entry = {'sample_index': index, 'accepted': reason is None, 'reason': reason}
        if reason is None:
            mapping[association['case_id']].append(index)
            entry['case_id'] = association['case_id']
            entry['turn_id'] = association['turn_id']
        audit.append(entry)
    return mapping, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=int, required=True)
    parser.add_argument('--partial', action='store_true')
    parser.add_argument('--runner', type=Path, default=DEFAULT_RUNNER,
                        help='Exact runner file used, if root moved the proposal; hash must match PREREG')
    args = parser.parse_args()
    require(args.batch > 803, 'Expected root-assigned app batch above803')
    private = Path(os.environ['LOCALAPPDATA']) / f'BAXY/C03-app-open-runner{args.batch}-private'
    public = ROOT / f'artifacts/comprobaciones/C03/APPLICATION_OPEN{args.batch}'
    prereg = read(public / 'PREREG.json')
    require(prereg['batch'] == args.batch, 'Wrong prereg batch')
    require(Path(prereg['private']).resolve() == private.resolve(), 'Wrong private path')
    plan_path = ROOT / 'artifacts/comprobaciones/C03/NEXT_APPLICATION_CATEGORY.json'
    require(sha(plan_path) == prereg['plan_sha256'], 'Plan seal differs')
    plan = read(plan_path)
    panel_path = Path(plan['panel_path'])
    require(sha(panel_path) == plan['panel_sha256'] == prereg['panel_sha256'], 'Original panel seal differs')
    require(sha(private / 'panel.json') == prereg['panel_sha256'], 'Private panel seal differs')
    require(sha(args.runner) == prereg['runner_sha256'], 'Runner seal differs')
    panel = read(panel_path)
    require(len(panel) == plan['case_count'] == 75 and len({c['case_id'] for c in panel}) == 75,
            'Expected75 unique registered cases')
    require([{key: case[key] for key in ('case_id', 'group', 'origin', 'criterion')} for case in panel]
            == prereg['cases'], 'Preregistered case metadata/order differs')
    require(sha(private / 'turns.jsonl') == prereg['turns_sha256'], 'Turns file seal differs')
    turns = rows(private / 'turns.jsonl', False, [])
    require(turns == [{'cmd': 'turn', 'text': case['text']} for case in panel], 'Turn text/order differs')
    pins = prereg['dependency']['pins']
    require(bool(pins) and read(Path(prereg['dependency']['source_pins'])) == pins, 'Dependency pins differ')
    full_path = Path(prereg['dependency']['full_exit'])
    require(sha(full_path) == prereg['dependency']['full_exit_sha256'], 'Full receipt differs')
    full = read(full_path)
    require(full['exit_code'] == 0 and full['source_pins_unchanged'] is True, 'Full did not pass')
    require(full['source_pins_sha256'] == sha(Path(prereg['dependency']['source_pins'])), 'Full pins differ')
    for name, digest in {**prereg['sources'], **pins}.items():
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT.resolve()) and sha(path) == digest, f'Source seal differs: {name}')
    outcome_path = public / 'EXIT.json'
    outcome = read(outcome_path) if outcome_path.exists() else None
    if not args.partial:
        require(outcome is not None, 'Final EXIT missing; use --partial for incomplete runs')
        require(outcome['exit_code'] == outcome['runner_exit_code'] == 0, 'Run did not exit cleanly; use --partial')
        for key in ('panel_unchanged', 'plan_unchanged', 'manifest_unchanged', 'sources_unchanged',
                    'dependency_sources_unchanged', 'runner_unchanged', 'app_dll_unchanged'):
            require(outcome[key] is True, f'Failed exit seal: {key}')
        require(not outcome['runner_violations'], 'Runner violations present')
        require(outcome['observed_terminals'] == 75, 'Runner observed an incomplete panel')
        resources = read(public / 'RESOURCES.json')
        require(not resources['violations'] and resources['gpu_telemetry_available'] is True,
                'Resources lack a clean observed result')
    truncated = []
    names = ('capture/events.jsonl', 'shell-trace.jsonl', 'compose-audit.jsonl',
             'turn-audit.jsonl', 'raw-replies.jsonl', 'windows-timeline.jsonl')
    captured = {name: rows(private / name, args.partial, truncated) for name in names}
    review = correlate(panel, *(captured[name] for name in names[:5]))
    sample_mapping, association_audit = associate_samples(
        panel, captured['shell-trace.jsonl'], captured['windows-timeline.jsonl'])
    for case in review:
        indices = sample_mapping[case['case_id']]
        if indices:
            case['independent_windows'] = {
                'association': 'trace_bookends', 'sample_indices': indices,
                'meaning': 'Observation bracketed within the same last-started turn after a core call ended; no UTC conversion, success judgment or causal attribution.'}
    if not args.partial:
        require(len(review) == 75, 'Final correlation needs75 terminals')
    snapshots = {}
    for name in ('windows-before.json', 'windows-after.json'):
        path = private / name
        if path.exists():
            snapshots[name] = read(path)
        elif not args.partial:
            raise ValueError(f'Missing independent observation: {name}')
    payload = {'batch': args.batch, 'partial': args.partial, 'registered_total': 75,
               'completed_terminals': len(review), 'quality_adjudicated': False,
               'root_judgment': 'pending', 'exit': outcome, 'truncated_tails': truncated,
               'cases': review, 'raw_captures': captured, 'panel_snapshots': snapshots,
               'timeline_association': 'Only validated trace_bookends link samples; legacy, null or invalid associations remain unassigned. Core completion is not success.',
               'sample_mapping': sample_mapping, 'association_audit': association_audit}
    prefix = 'apps-review-partial' if args.partial else 'apps-review'
    (private / f'{prefix}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    markdown = [f'# Aplicaciones · tanda{args.batch}',
                f'{len(review)}/75 finales correlacionados. Juicio de calidad pendiente de raíz.',
                'Observaciones vinculadas sólo cuando trace_bookends supera validación; muestras antiguas o inválidas permanecen sin asignar. No acredita éxito.']
    for case in review:
        markdown.extend([f"## {case['case_id']} · {case['turn_id']}",
                         '**Entrada:**\n\n' + case['text'],
                         '**Respuesta:**\n\n' + str(case['terminal'].get('final') or ''),
                         '**Criterio pendiente de juicio raíz:**\n\n' + case['criterion'],
                         f"**Muestras independientes verificadas por orden:** {case['independent_windows']['sample_indices']}.",
                         '**Juicio raíz:** pendiente.'])
    (private / f'{prefix}.md').write_text('\n\n'.join(markdown) + '\n', encoding='utf-8')
    print(json.dumps({key: payload[key] for key in ('batch', 'partial', 'registered_total', 'completed_terminals', 'quality_adjudicated')}))


if __name__ == '__main__':
    main()
