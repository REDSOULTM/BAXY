"""Adopt the measured bounded instruction and preserve every product outcome."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base/'astra-window-scope-product653'
private = home/'C03-window-scope-product653-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
assert sha(private/'panel.json') == sha(home/'C03-context-product647-private/panel.json')
panel = read(private/'panel.json')
events = rows(private/'capture/events.jsonl')
finals = [r for r in events if r.get('type') == 'terminal']
compose = rows(private/'compose-audit.jsonl')
observations = {r['trace']: r['payload'] for r in compose if r.get('published') and r.get('payload', {}).get('operation')}
assert len(panel) == len(finals) == 20 and len(observations) == 18
visible = [r['event']['entry']['msg'] for r in events if r.get('type') == 'event'
           and r['event'].get('type') == 'activity' and r['event']['entry']['src'] == 'BAXY']
assert visible == [r['final'] for r in finals]
snapshots = {name: read(private/f'windows-{name}.json') for name in ['before', 'after']}
assert not any(row['identity_error'] for s in snapshots.values() for row in s['windows'])
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
assert counts['before'] == counts['after'] == {
    'Steam': 2, 'Google Chrome': 2, 'WhatsApp': 1, 'Spotify': 0, 'Paint': 0, 'Bloc de notas': 0,
}
adjudication = []
for index, (case, final) in enumerate(zip(panel, finals), 1):
    assert final['kind'] == 'published_final' and final['timedOut'] is False
    observed = observations.get(f't{index}')
    if case['operation']:
        assert observed['operation'] == case['operation']
    else:
        assert observed is None
    if case['name']:
        assert observed['seen']['requestedName'] == case['name']
        assert observed['seen']['visibleWindowCount'] == counts['before'][case['name']]
    failed = case['case_id'] == 'focus-en'
    adjudication.append({**case, 'terminal': final, 'observation': observed,
        'verdict': 'failed' if failed else 'correct',
        'reason': ('English request is still classified mixed and answered in Spanish; foreground observation itself is correct.' if failed
            else 'Meets the complete request, language and observed scope; preserves the current name/count and does not infer process liveness.')})
assert sum(r['verdict'] == 'correct' for r in adjudication) == 19
assert finals[14]['final'] == 'Spotify is installed but no visible windows are currently open.'
write(private/'adjudication.json', adjudication)
report = ['# Producto 653: 19/20 finales correctos']
for r in adjudication:
    report += ['## '+r['case_id'], r['text'], r['terminal']['final'], r['verdict']+': '+r['reason'],
               json.dumps(r['observation'], ensure_ascii=False)]
report += ['## Actividad y comprobación independiente',
    'Durante los veinte turnos: veinte mensajes BAXY de actividad, iguales a los veinte finales; sin progreso adicional. La bienvenida t0 está en el diagnóstico de composición y se conserva aparte, sin crédito de UI.',
    json.dumps(counts, ensure_ascii=False),
    'Cada fila HWND registra AUMID, creación e identidad durante la captura. No son metadatos consultados después de la campaña; no se declara una instantánea atómica de todas las ventanas.']
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n', encoding='utf-8', newline='\n')
note = '''# 653: prosa de ventanas veraz en el panel; idioma del foco pendiente

El mismo panel de veinte casos de 647 obtiene 19/20 finales correctos, frente a 18/20. La frase de Spotify ya se limita a instalación y ausencia de ventanas visibles; no añade que el proceso esté ejecutándose. Las 16 lecturas por aplicación conservan nombre, cantidad y las cuatro referencias. El único fallo del panel es «Which window has focus?» respondido en español.

Los veinte mensajes BAXY de actividad durante los turnos coinciden con los veinte finales, sin progreso adicional. La bienvenida t0 se conserva en el diagnóstico de composición; esto no es inspección de una interfaz real. Las capturas independientes antes/después coinciden con las lecturas: Steam 2, Chrome 2, WhatsApp 1, y cero para Spotify, Paint y Bloc de notas. WhatsApp ahora tiene una ventana y Chrome dos: difieren de 647 y se responde con las cantidades actuales. AUMID, creación y errores se capturan con cada fila HWND, siguiendo la corrección del verificador 648; no hubo errores de identidad.

Recursos: GPU 3497,559 MiB, RAM 1626,023 MiB y 38,203 s, sin infracciones y con registro intacto. No es una comparación emparejada de RAM/latencia ni un mínimo de BAXY completo; no acredita UI/voz conjunta. El contrato factual 649 sigue incompleto, aunque esta generación corrige el caso real observado. Encuesta al medir: 25 cubiertos, 717 abiertos, 0 no aplicables; H0040 dispone ahora de evidencia favorable para su actualización individual.
'''
seal(out, private, {'utc': datetime.now(timezone.utc).isoformat(), 'source': 652,
    'correct': 19, 'total': 20, 'failed_cases': ['focus-en'], 'named_application_reads_correct': 16,
    'contextual_fresh_reads_correct': 4, 'visible_activity_matches_finals': True,
    'independent_counts': counts, 'aumid_captured_with_window_rows': True,
    'resources': read(out/'resources.json'), 'ui_or_voice_credit': False,
    'factual_validator649_repaired': False}, note,
    ['panel.json', 'capture/events.jsonl', 'compose-audit.jsonl', 'turn-audit.jsonl', 'shell-trace.jsonl',
     'raw-replies.jsonl', 'windows-before.json', 'windows-after.json', 'adjudication.json', 'RESULT.md'])

out = base/'astra-window-scope-source652'
assert not (out/'RESULT.json').exists()
pins = read(out/'SOURCE.json')
assert sha(root/'src/baxy_mind/llm.py') == pins['llm_sha256']
assert all(sha(root/p) == value for p, value in pins['current_declarations'].items())
temp = Path(os.environ['TEMP'])
assert (temp/'c03-window-scope652-fast-exit.txt').read_text().strip() == '0'
for original, target in [('c03-window-scope652-owners.log', 'OWNERS.log'), ('c03-window-scope652-pins.log', 'DECLARATIONS.log'), ('c03-window-scope652-fast.log', 'FAST.log')]:
    (out/target).write_bytes((temp/original).read_bytes())
assert '3902 passed, 121 subtests passed' in (out/'OWNERS.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out/'FAST.log').read_text(encoding='utf-8-sig')
source_note = '''# 652: alcance de la observación integrado en el escritor

Se integra exactamente la instrucción de sistema medida en 650 para lecturas verificadas y correctas de window.application.status con instalación y cantidad observadas. Se conserva también en el reintento existente. No afecta progreso, fallos, conversaciones, otras lecturas ni misiones de varios pasos. No añade modelo, estado, comprobación paralela ni frases visibles fijas.

Validación: 16 payloads iguales a los brazos medidos de 650 y nueve controles de otras rutas sin cambios. Dueñas: 3902 pases + 121 subpruebas, sin skips, en 72,36 s. Declaraciones: 17 pases y 1 skip ambiental en 1,87 s. Fast exit 0, Release 27,28 s, sin advertencias o errores. Producto 653: 19/20 finales y 16/16 consultas por aplicación correctas; el foco inglés sigue en español. Se adopta esta fuente Python; Full 651 es la línea base anterior, no un Full de 652 ni cierre global.

El validador 649 aún acepta contradicciones y estados de proceso sin observar. Esta mejora del primer borrador no lo da por reparado. Sigue el trabajo de C03 sobre ese contrato, idioma, encuesta, UI real, voz, recuperación y Full final. Modelo, perfil y backend permanecen iguales.
'''
seal(out, home, {'utc': datetime.now(timezone.utc).isoformat(), 'adopted': True,
    'llm_sha256': pins['llm_sha256'], 'python_tree_sha256': pins['python_tree_sha256'],
    'parity_checks': 25, 'owners': {'passed': 3902, 'subtests': 121, 'skipped': 0, 'seconds': 72.36},
    'declarations': {'passed': 17, 'environmental_skipped': 1}, 'fast_exit': 0,
    'release_seconds': 27.28, 'full_baseline': 651, 'full652_run': False,
    'product653_correct': 19, 'product653_total': 20, 'goal_complete': False}, source_note, [])
state = read(base/'RELEVO_ACTIVO.json')
state.pop('activeCampaign', None)
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='652 adoptada:3902dueñas/Fast0,653 producto19/20 y16/16consultas aplicación.6507/8→8/8. Publicación pendiente;26 sólo tras actualizarH0040.',
    continuation='Actualizar H0040 con evidencia653 y recuentos reales; auditar/publicar650+652+653. Después reparar contrato factual649 e idiomahas. No campañas activas.')
write(base/'RELEVO_ACTIVO.json', state)
print({'source652_adopted': True, 'product653_correct': 19, 'goal_complete': False})
