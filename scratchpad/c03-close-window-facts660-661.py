"""Seal reviewed regression661 and adopt the bounded factual contract660."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base / 'astra-window-facts-product661'
private = home / 'C03-window-facts-product661-private'
assert not (out / 'RESULT.json').exists()
assert read(out / 'EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
prereg = read(out / 'PREREG.json')
assert all(sha(root / name) == value for name, value in prereg['sources'].items())
panel = read(private / 'panel.json')
old = home / 'C03-language-product655-private'
assert panel == read(old / 'panel.json')
events = rows(private / 'capture/events.jsonl')
finals = [r for r in events if r.get('type') == 'terminal']
old_finals = [r for r in rows(old / 'capture/events.jsonl') if r.get('type') == 'terminal']
assert len(panel) == len(finals) == 24
assert [r['final'] for r in finals] == [r['final'] for r in old_finals]
visible = [r['event']['entry']['msg'] for r in events if r.get('type') == 'event' and r['event'].get('type') == 'activity' and r['event']['entry']['src'] == 'BAXY']
assert visible == [r['final'] for r in finals]
observations = {r['trace']: r['payload'] for r in rows(private / 'compose-audit.jsonl') if r.get('published') and r.get('payload', {}).get('operation')}
assert len(observations) == 22
snapshots = {name: read(private / f'windows-{name}.json') for name in ['before', 'after']}
assert snapshots['before']['foreground'] == snapshots['after']['foreground']
assert not any(r['identity_error'] for s in snapshots.values() for r in s['windows'])
counts = {}
for name, snapshot in snapshots.items():
    windows = snapshot['windows']
    counts[name] = {
        'Steam': sum(r['process'] == 'steamwebhelper.exe' for r in windows),
        'Google Chrome': sum(r['process'] == 'chrome.exe' for r in windows),
        'WhatsApp': sum(r['aumid'] == '5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App' for r in windows),
        'Spotify': sum(r['process'].lower() == 'spotify.exe' for r in windows),
        'Paint': sum(r['process'].lower() == 'mspaint.exe' for r in windows),
        'Bloc de notas': sum(r['process'].lower() == 'notepad.exe' for r in windows),
    }
assert counts['before'] == counts['after']
adjudication = []
for i, (case, final) in enumerate(zip(panel, finals), 1):
    assert final['kind'] == 'published_final' and not final['timedOut']
    observed = observations.get(f't{i}')
    if case['operation']:
        assert observed['operation'] == case['operation']
    else:
        assert observed is None
    if case['name']:
        assert observed['seen']['requestedName'] == case['name']
        assert observed['seen']['visibleWindowCount'] == counts['before'][case['name']]
    elif case['operation'] == 'window.active':
        assert observed['seen']['windows'][0]['title'] == snapshots['before']['foreground']['title']
        assert observed['seen']['windows'][0]['foreground'] is True
    failed = case['case_id'] == 'focus-variant-es'
    adjudication.append({**case, 'terminal': final, 'observation': observed,
        'verdict': 'failed' if failed else 'correct',
        'reason': 'Reproduces655: correct state but unnecessary internal English word foreground in Spanish.' if failed else 'Individually reviewed: request, language, observed subject/count and scope preserved; fresh references correct.'})
write(private / 'adjudication.json', adjudication)
report = ['# Producto661 — 23/24, sin cambios en los24 finales de655']
for row in adjudication:
    report += ['## '+row['case_id'], row['text'], row['terminal']['final'], row['verdict']+': '+row['reason'], json.dumps(row['observation'], ensure_ascii=False)]
report += ['## Capturas independientes', json.dumps(counts, ensure_ascii=False), json.dumps({k:v['foreground'] for k,v in snapshots.items()}, ensure_ascii=False), 'Antes/después coinciden; no captura continua ni atómica. Actividad igual a finales. Sin crédito de UI/voz.']
(private / 'RESULT.md').write_text('\n\n'.join(report)+'\n', encoding='utf-8', newline='\n')
note = '''# 661 — contrato factual sin regresión en el panel de producto

Las24 respuestas finales coinciden literalmente con655. Se revisaron individualmente contra las22 observaciones y capturas independientes antes/después:23/24 correctas,16 lecturas de aplicaciones y cuatro referencias preservadas. Sigue el fallo de naturalidad español «foreground» en t24; no se considera reparado. Las24 actividades coinciden con los24 finales. AUMID sin errores y cantidades/foco estables entre capturas, sin crédito de observación continua.

GPU3497,559MiB, RAM2192,313MiB y38,875s, sin infracciones. No medición conjunta de UI/voz, mínimo global ni comparación emparejada de ahorro. Fuente/modelo/registro intactos durante la corrida. Este panel prueba ausencia de regresión observada; la mejora del rechazo factual se demuestra en660 con el compositor y transporte simulado, no mediante borradores inyectados en este producto. Encuesta26/716/0, sin nueva cobertura individual.
'''
seal(out, private, {'source':660, 'correct':23, 'total':24, 'all_finals_identical_to655':True,
    'application_reads_correct':16, 'contextual_fresh_reads_correct':4,
    'failed_cases':['focus-variant-es'], 'resources':read(out/'resources.json'),
    'visible_activity_matches_finals':True, 'independent_counts':counts,
    'foreground_snapshots_agree':True, 'ui_or_voice_credit':False}, note,
    ['panel.json','capture/events.jsonl','compose-audit.jsonl','turn-audit.jsonl','shell-trace.jsonl',
     'raw-replies.jsonl','windows-before.json','windows-after.json','adjudication.json','RESULT.md'])
out = base / 'astra-window-facts-source660'
assert not (out / 'RESULT.json').exists()
source_pin = read(out / 'PREREG.json')
assert all(sha(root / name) == value for name, value in source_pin['sources'].items())
temp = Path(os.environ['TEMP'])
for suffix in ['owners','fast']:
    assert (temp / f'c03-window-facts660-{suffix}.exit.txt').read_text().strip() == '0'
for original, dest in [('owners','OWNERS'),('pins','DECLARATIONS'),('fast','FAST')]:
    (out / f'{dest}.log').write_bytes((temp / f'c03-window-facts660-{original}.log').read_bytes())
assert '4046 passed, 121 subtests passed' in (out / 'OWNERS.log').read_text(encoding='utf-8-sig')
assert '22 passed, 1 skipped' in (out / 'DECLARATIONS.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'FAST.log').read_text(encoding='utf-8-sig')
note = '''# 660 — hechos de ventanas conservados en el compositor

Se adopta una extensión delimitada del contrato factual existente: contrasta instalación, cantidades/rangos y afirmaciones de proceso con los campos tipados de window.application.status. Mantiene nombres, negaciones, desconocimiento explícito y otras operaciones. Una aclaración legítima sobre procesos no convierte una respuesta completa de ventanas en fallo; una respuesta que sólo desconoce el proceso sigue siendo insuficiente. No se añade modelo, inferencia ni respuesta visible fija.

Misma cohorte104: fuente publicada65460 fallos/44 pases; candidata104 pases. Incluye compositor completo con transporte simulado: cuatro borradores incorrectos se rechazan y reintentan; respuestas válidas salen en una llamada. Esto corrige la evidencia parcial649, que sólo llamaba compose_visible_defect. Se conservan baseline inicial, refinamiento de una respuesta incompleta y controles expandidos, sin cambiar el criterio para aprobar. No es prueba semántica universal: gramática acotada, sin cobertura universal de sujetos ajenos o todas las formas numéricas.

Dueñas4046 pases+121 subpruebas,0 skips,70,46s. Declaraciones22 pases/1 skip ambiental,2,01s. Fast exit0,Release27,99s,0 advertencias/errores. Producto661 conserva23/24 y todos los finales655, incluida la jerga española pendiente. Full651 sigue siendo línea base anterior; no Full660 ni cierre global. Encuesta26/716/0. Siguiente: aislar fuga del metadato en prosa de foco y seguir cobertura, UI/voz, recuperación y Full final.
'''
seal(out, out, {'adopted':True, 'sources':source_pin['sources'], 'python_tree_sha256':source_pin['python_tree_sha256'],
    'same_cohort_baseline':{'failed':60,'passed':44}, 'focal_passed':104,
    'owners':{'passed':4046,'subtests':121,'skipped':0,'seconds':70.46},
    'declarations':{'passed':22,'environmental_skipped':1,'seconds':2.01},
    'fast_exit':0,'release_seconds':27.99,'full_baseline':651,'full660_run':False,
    'product661_correct':23,'product661_total':24,'goal_complete':False}, note, [])
state_path = base / 'RELEVO_ACTIVO.json'
state = read(state_path)
state.update(checkpoint='660 adoptada;661 conserva23/24. Contrato factual acotado verificado. Encuesta26/716/0.',
    continuation='Auditar/publicar660–661. Seguir fuga foreground655/661, encuesta y cierreC03. Ninguna decisión pendiente ni proceso activo.', activeValidation=None)
write(state_path, state)
with (base / 'HANDOFF.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n## Adopción660/661 — vigente\n\n'+note+'\nSesiones79799/85214/6196 recogidas exit0; ninguna activa. Close660-661 ejecutado, no repetir. Publicar antes de nueva fuente.\n')
print({'adopted':660, 'product661':'23/24', 'survey':'26/716/0', 'goal_complete':False})
