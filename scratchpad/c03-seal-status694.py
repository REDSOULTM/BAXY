"""Seal694 only after every final has an explicit evidence-based adjudication."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
helper = (root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(helper[:helper.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base/'astra-status-batch694'
private = home/'C03-status-batch694-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
review = read(private/'review.json')
verdicts = read(private/'verdicts.json')
assert len(review) == 73 and set(verdicts) == {r['case_id'] for r in review}
assert (private/'panel.json').read_bytes() == (home/'C03-status-batch689-private/panel.json').read_bytes()
prereg = read(out/'PREREG.json')
assert all(sha(root/name) == expected for name,expected in prereg['sources'].items())
plan = read(base/'STATUS_BATCH694_PLAN.json')
assert sha(root/'scratchpad/c03-status694-hook/sitecustomize.py') == plan['instrumentation_sha256']
assert sha(home/'C03-survey-requirements336-private/requirements.jsonl') == plan['requirements_sha256']
before = {r['case_id']: r for r in read(home/'C03-status-batch689-private/adjudication.json')}
adjudication = []
for row in review:
    verdict = verdicts[row['case_id']]
    assert set(verdict) == {'verdict', 'cause_group', 'reason'}
    assert verdict['verdict'] in {'correct_observed_run', 'failed', 'needs_verification'}
    assert isinstance(verdict['reason'], str) and len(verdict['reason']) >= 20
    if verdict['verdict'] == 'correct_observed_run':
        assert row['terminal']['kind'] == 'published_final' and row['core_calls'] and row['compose'], row['case_id']
    assert not row['terminal']['timedOut'], row['case_id']
    adjudication.append({**row, **verdict, 'before689': before[row['case_id']]['verdict']})
counts = dict(Counter(r['verdict'] for r in adjudication))
transitions = dict(Counter(r['before689']+' -> '+r['verdict'] for r in adjudication))
write(private/'adjudication.json', adjudication)
report = ['# Producto694: mismos73turnos, observación local del modelo',
    'Cada resultado se compara con su petición y observaciones frescas. El observador conserva llamadas, argumentos, resultados y errores. Las latencias incluyen su registro privado. No es aceptación ciega ni prueba de interfaz o voz. No se acredita cobertura automáticamente.',
    json.dumps({'counts': counts, 'transitions': transitions}, ensure_ascii=False)]
for row in adjudication:
    report += ['## '+row['case_id']+' — '+row['group'], row['text'],
        row['terminal']['final'], row['verdict']+': '+row['reason'],
        'Criterio: '+row['criterion'], json.dumps({'owner_review': row.get('owner_review'),
            'core_calls': row['core_calls'], 'decisions': row['decisions'], 'compose': row['compose']}, ensure_ascii=False)]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n', encoding='utf-8', newline='\n')
resources = read(out/'resources.json')
assert not resources['violations']
note = (private/'public-note.md').read_text(encoding='utf-8')
assert note.strip() and str(counts.get('correct_observed_run', 0)) in note
seal(out, private, {'requirements': 50, 'variants': 23, 'total': 73, 'counts': counts,
    'by_group': {g: dict(Counter(r['verdict'] for r in adjudication if r['group']==g)) for g in sorted({r['group'] for r in adjudication})},
    'transitions689': transitions,
    'cause_groups': dict(Counter(r['cause_group'] for r in adjudication if r['cause_group'])),
    'resources': resources, 'plan_sha256': sha(base/'STATUS_BATCH694_PLAN.json'),
    'transparent_observation_added': True, 'same_inputs_order_and_criteria689': True,
    'survey': {'covered': 26, 'open': 716, 'not_applicable': 0}, 'new_coverage': 0,
    'ui_or_voice_credit': False, 'goal_complete': False}, note,
    ['panel.json', 'turns.jsonl', 'capture/events.jsonl', 'compose-audit.jsonl', 'turn-audit.jsonl',
     'shell-trace.jsonl', 'raw-replies.jsonl', 'http-posts.jsonl', 'decision-boundary.jsonl',
     'verdicts.json', 'adjudication.json', 'RESULT.md'])
print(json.dumps({'counts': counts, 'transitions': transitions}, ensure_ascii=False))
