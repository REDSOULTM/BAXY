"""Adjudicate restored references without hiding the unsupported liveness claim."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base/'astra-package-scope648'; private = home/'C03-package-scope648-private'
assert not (out/'PINS.json').exists()
identity = read(out/'RESULT.json')
assert identity['matching_snapshot_window_counts'] == {'before': 2, 'after': 2}
assert {r['process'].casefold() for r in identity['matched_processes']} == {'whatsapp.root.exe', 'msedgewebview2.exe'}
note648 = '''# 648 — el conteo de un paquete incluye todos sus procesos

647 observó dos ventanas de WhatsApp. La comprobación independiente que contaba sólo WhatsApp.Root.exe encontraba una, porque otra ventana pertenece a msedgewebview2.exe con exactamente el mismo AUMID del paquete. Al agrupar los handles de las instantáneas por esa identidad, ambas contienen dos. La consulta de identidad se hizo después de647; los procesos mantienen nombres y tiempos de creación compatibles con ambas instantáneas. No se presenta esa identidad como una captura simultánea. Un PID ajeno ya había terminado; se conserva el error y no se atribuye a ningún actor.

No cambia el provider ni la fuente. El error era usar el nombre del ejecutable como comprobación independiente de una identidad empaquetada. Futuras instantáneas deben registrar AUMID junto al HWND/PID en el momento de captura. Sin nuevas ventanas, activación, mensajes, modelo ni crédito de UI/voz.
'''
(out/'RESULT.md').write_text(note648, encoding='utf-8', newline='\n')
write(out/'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root/'.gitattributes').open('a', encoding='utf-8', newline='\n') as f:
    f.write('/artifacts/comprobaciones/C03/astra-package-scope648/** -text\n')
with (base/'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as f: f.write('\n\n'+note648)

out = base/'astra-context-product647'; private = home/'C03-context-product647-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
panel = read(private/'panel.json')
assert sha(private/'panel.json') == sha(home/'C03-count-product642-private/panel.json')
events = rows(private/'capture/events.jsonl')
finals = [r for r in events if r.get('type') == 'terminal']; assert len(finals) == len(panel) == 20
observations = {r['trace']: r['payload'] for r in rows(private/'compose-audit.jsonl') if r.get('payload', {}).get('operation')}
snapshots = {key: read(private/f'windows-{key}.json') for key in ['before', 'after']}
process_names = {'Steam': 'steamwebhelper.exe', 'Google Chrome': 'chrome.exe', 'Bloc de notas': 'notepad.exe', 'Spotify': 'spotify.exe', 'Paint': 'mspaint.exe'}
for i in [*range(1, 9), *range(13, 21)]:
    name = panel[i-1]['name']; observation = observations[f't{i}']
    assert observation['operation'] == 'window.application.status'
    seen = observation['seen']; assert seen['requestedName'] == name
    for key, snapshot in snapshots.items():
        count = identity['matching_snapshot_window_counts'][key] if name == 'WhatsApp' else sum(r['process'].casefold() == process_names[name] for r in snapshot['windows'])
        assert seen['visibleWindowCount'] == count, (i, seen, count)
failures = {
    'focus-en': 'English focus question still classified mixed and answered in Spanish.',
    'reference-new-name-en': 'Selection, reference and read are repaired, but first published draft claims Spotify is running. The payload establishes installed=true and visibleWindowCount=0 only; process liveness was not observed.',
}
judged = [{**case, 'terminal': final, 'observation': observations.get(f't{i}'),
    'verdict': 'failed' if case['case_id'] in failures else 'correct',
    'reason': failures.get(case['case_id'], 'Preserves requested scope, actual observation and language.')}
    for i, (case, final) in enumerate(zip(panel, finals), 1)]
write(private/'adjudication.json', judged)
report = ['# 647 — 18/20 finales; 16 lecturas por aplicación con nombre correcto']
for r in judged:
    report += ['## '+r['case_id'], r['text'], r['terminal']['final'], r['verdict']+': '+r['reason'], json.dumps(r['observation'], ensure_ascii=False)]
report += ['## Límite de la comprobación independiente', note648]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n', encoding='utf-8', newline='\n')
messages = [r['event']['entry'] for r in events if r.get('event', {}).get('type') == 'activity' and r['event']['entry'].get('src') == 'BAXY']
assert len(messages) == 20
assert {r['msg'] for r in messages} == {r['final'] for r in finals}
note647 = '''# 647 — referencias verificadas, una afirmación posterior sin respaldo

Mismo panel de20casos642:18 finales acreditados frente a15. Las cuatro referencias t15–t18 ya ejecutan window.application.status con Spotify/Steam correctos y una lectura nueva. Las16lecturas por aplicación conservan nombre y cantidad. No se toca el texto original ni se sustituye el modelo: la selección y la extracción usan la misma referencia acotada de las preguntas del usuario; el shell transporta su historial existente a argumentos.

t15 falla después de leer: «Spotify is installed and running, but no window is currently visible.» El primer borrador publicado añade running; el payload sólo prueba instalación y ausencia de ventanas visibles. No se afirma que Spotify esté detenido: simplemente no se observó su proceso. El foco inglés conserva el fallo mixed→español. H0040 permanece abierto y no se acredita sólo porque las referencias lleguen al provider. No hubo prosa de progreso adicional:20 mensajes visibles corresponden a los20 finales.

Recursos: GPU3497,559MiB, RAM2290,973MiB,91,563s incluyen NativeAOT; sin infracciones. Fuente y registro intactos durante647. La comprobación independiente de WhatsApp se completa con648, que identifica dos procesos del mismo paquete; se conserva explícitamente que esa identidad se consultó después de las instantáneas. No UI/voz conjunta ni mínimo global. Full646 debe concluir verde antes de adoptar el cambio combinado; encuesta25/717/0.
'''
seal(out, private, {'source': 646, 'correct': 18, 'total': 20, 'failed_cases': failures,
    'named_queries_with_correct_scope_and_count': 16, 'contextual_fresh_reads_repaired': 4,
    'packaged_process_identity_addendum': 'astra-package-scope648',
    'packaged_identity_captured_later': True, 'extra_visible_progress_messages': 0,
    'resources': read(out/'resources.json'), 'ui_or_voice_credit': False,
    'whole_window_requirement_accepted': False}, note647,
    ['panel.json', 'capture/events.jsonl', 'compose-audit.jsonl', 'turn-audit.jsonl',
     'raw-replies.jsonl', 'shell-trace.jsonl', 'adjudication.json', 'RESULT.md',
     'windows-before.json', 'windows-after.json'])
print({'product647_correct': 18, 'contextual_fresh_reads': 4, 'survey': '25/717/0'})
