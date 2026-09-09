"""Adopt the language reader, preserving the new foreground prose failure."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base / 'astra-language-product655'
private = home / 'C03-language-product655-private'
assert not (out / 'RESULT.json').exists()
assert read(out / 'EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
prereg = read(out / 'PREREG.json')
assert all(sha(root / name) == value for name, value in prereg['sources'].items())
panel = read(private / 'panel.json')
assert panel[:20] == read(home / 'C03-window-scope-product653-private/panel.json')
events = rows(private / 'capture/events.jsonl')
finals = [r for r in events if r.get('type') == 'terminal']
old_finals = [r for r in rows(home / 'C03-window-scope-product653-private/capture/events.jsonl') if r.get('type') == 'terminal']
assert len(finals) == len(panel) == 24
assert [i + 1 for i, (a, b) in enumerate(zip(old_finals, finals[:20])) if a['final'] != b['final']] == [10]
assert finals[9]['final'] == 'The ChatGPT window has focus.'
assert finals[-1]['final'] == 'La ventana activa es ChatGPT. Está maximizada y está en el foreground.'
visible = [r['event']['entry']['msg'] for r in events if r.get('type') == 'event' and r['event'].get('type') == 'activity' and r['event']['entry']['src'] == 'BAXY']
assert visible == [r['final'] for r in finals]
compose = rows(private / 'compose-audit.jsonl')
observations = {r['trace']: r['payload'] for r in compose if r.get('published') and r.get('payload', {}).get('operation')}
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
        'reason': 'Identifies the correct foreground window, but imports the English internal field word foreground into a Spanish reply. Naturalness failure; not an invented state.' if failed else 'Correct request, language, observed scope and subject. Preserves current counts and fresh references.'})
write(private / 'adjudication.json', adjudication)
report = ['# Producto655 — 23/24; panel original20/20']
for r in adjudication:
    report += ['## '+r['case_id'], r['text'], r['terminal']['final'], r['verdict']+': '+r['reason'], json.dumps(r['observation'], ensure_ascii=False)]
report += ['## Comprobación independiente', json.dumps(counts, ensure_ascii=False),
           json.dumps({k: v['foreground'] for k, v in snapshots.items()}, ensure_ascii=False),
           'Snapshots before/after agree; no claim of a continuous or atomic foreground capture. All24 activity messages equal the24 finals. No UI or voice credit.']
(private / 'RESULT.md').write_text('\n\n'.join(report)+'\n', encoding='utf-8', newline='\n')
note = '''# 655 — idioma inglés reparado, naturalidad pendiente en una variante

El panel original653 mejora de19/20 a20/20; sólo cambia el final10: «The ChatGPT window has focus.». Las cuatro variantes añadidas dan3/4. La última responde «La ventana activa es ChatGPT. Está maximizada y está en el foreground.»: hechos conservados, pero tecnicismo inglés innecesario en español. Se cuenta como fallo de naturalidad; no se atribuye a una regresión de654 sin comparación anterior de esa variante. Total23/24.

Las16 lecturas por aplicación, cantidades y cuatro referencias siguen correctas. Los24 mensajes de actividad coinciden con los24 finales. Capturas independientes con AUMID sin errores, cantidades y título/handle de primer plano coinciden antes/después; no equivalen a observación continua ni atómica. GPU3497,559MiB,RAM1864,781MiB,37,766s,sin infracciones. No mínimo global ni comparación de ahorro; UI/voz conjunta no acreditadas. Registro/modelo intactos. Encuesta26/716/0; no se acredita otra fila por pertenecer a la misma familia.
'''
seal(out, private, {'source': 654, 'correct': 23, 'total': 24, 'original_panel_correct': 20,
    'failed_cases': ['focus-variant-es'], 'application_reads_correct': 16,
    'contextual_fresh_reads_correct': 4, 'changed_original_final_indices': [10],
    'visible_activity_matches_finals': True, 'independent_counts': counts,
    'foreground_snapshots_agree': True, 'continuous_foreground_credit': False,
    'resources': read(out / 'resources.json'), 'ui_or_voice_credit': False,
    'factual_validator649_repaired': False}, note,
    ['panel.json', 'capture/events.jsonl', 'compose-audit.jsonl', 'turn-audit.jsonl', 'shell-trace.jsonl',
     'raw-replies.jsonl', 'windows-before.json', 'windows-after.json', 'adjudication.json', 'RESULT.md'])
out = base / 'astra-language-source654'
assert not (out / 'RESULT.json').exists()
source_pin = read(out / 'PREREG.json')
assert sha(root / 'src/baxy_mind/request_reading.py') == source_pin['reader_sha256']
temp = Path(os.environ['TEMP'])
assert (temp / 'c03-language654-owners-exit.txt').read_text().strip() == '0'
assert (temp / 'c03-language654-fast-exit.txt').read_text().strip() == '0'
for original, dest in [('c03-language654-owners.log', 'OWNERS.log'), ('c03-language654-pins.log', 'DECLARATIONS.log'), ('c03-language654-fast.log', 'FAST.log')]:
    (out / dest).write_bytes((temp / original).read_bytes())
assert '3942 passed, 121 subtests passed' in (out / 'OWNERS.log').read_text(encoding='utf-8-sig')
assert '22 passed, 1 skipped' in (out / 'DECLARATIONS.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'FAST.log').read_text(encoding='utf-8-sig')
note = '''# 654 — lector de idioma adoptado

La palabra compartida «has» deja de contarse como exclusivamente española. Las tablas existentes incorporan participios frecuentes inequívocos para conservar preguntas españolas y mixtas. No se añaden nombres de apps, reglas por sufijo, modelo, reintento ni prosa fija. Es una corrección del vocabulario finito existente, no detección universal de idioma.

Baseline13 fallos/27 pases en40 controles cruzados ES/EN/historia; dueña300 pases. Integradas3942 pases+121 subpruebas/0 skips,71,00s. Declaraciones22 pases/1 skip ambiental,2,56s. Fast0,Release27,65s,sin advertencias/errores. Producto655: panel original20/20; ampliado23/24, inglés reparado y una variante española con jerga pendiente. Se adopta la fuente del lector; contrato factual649 sigue abierto. Full651 es línea base anterior, no Full654 ni cierre. Encuesta26/716/0, ninguna decisión del dueño pendiente.
'''
seal(out, out, {'adopted': True, 'reader_sha256': source_pin['reader_sha256'],
    'python_tree_sha256': source_pin['python_tree_sha256'], 'llm_unchanged_sha256': source_pin['llm_unchanged_sha256'],
    'owners': {'passed': 3942, 'subtests': 121, 'skipped': 0, 'seconds': 71.00},
    'declarations': {'passed': 22, 'environmental_skipped': 1, 'seconds': 2.56},
    'fast_exit': 0, 'release_seconds': 27.65, 'full_baseline': 651, 'full654_run': False,
    'product655_correct': 23, 'product655_total': 24, 'goal_complete': False}, note, [])
state_path = base / 'RELEVO_ACTIVO.json'
state = read(state_path)
state.update(checkpoint='654 adoptada;655 panel original20/20, ampliado23/24. Idioma inglés reparado; jerga española y contrato649 pendientes.',
             continuation='Auditar/publicar654/655; continuar contrato factual649 y prosa sin jerga. Encuesta26/716/0. No campañas activas.', activeValidation=None)
write(state_path, state)
with (base / 'HANDOFF.md').open('a', encoding='utf-8', newline='\n') as f:
    f.write('\n\n## Actualización654/655 — manda sobre el siguiente anterior\n\n'+note+'\nScripts prepare654/close654-655 ya ejecutados; no repetir. Sesiones87181,44842,23598 recogidas exit0. Fuente actual reader SHA '+source_pin['reader_sha256']+'; árbolPython '+source_pin['python_tree_sha256']+'. Publicar654/655 antes de nueva fuente. Ninguna campaña activa.\n')
print({'source654_adopted': True, 'product655': '23/24', 'original_panel': '20/20', 'survey': '26/716/0'})
