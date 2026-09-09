"""Adopt count request preservation only after a fresh product observation."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base/'astra-count-product642'
private = home/'C03-count-product642-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
panel = read(private/'panel.json')
assert sha(private/'panel.json') == sha(home/'C03-window-reference-product640-private/panel.json')
finals = [r for r in rows(private/'capture/events.jsonl') if r.get('type') == 'terminal']
assert len(panel) == len(finals) == 20
observations = {r['trace']: r['payload'] for r in rows(private/'compose-audit.jsonl') if r.get('payload', {}).get('operation')}
before = read(private/'windows-before.json'); after = read(private/'windows-after.json')
assert before['windows'] == after['windows']
counts = Counter(r['process'].casefold() for r in before['windows'])
processes = {'Steam': 'steamwebhelper.exe', 'Google Chrome': 'chrome.exe', 'Bloc de notas': 'notepad.exe', 'Spotify': 'spotify.exe', 'Paint': 'mspaint.exe', 'WhatsApp': 'whatsapp.root.exe'}
for i in [*range(1, 9), 13, 14, 19, 20]:
    case = panel[i-1]; observation = observations[f't{i}']
    assert observation['operation'] == 'window.application.status'
    seen = observation['seen']
    assert seen['requestedName'] == case['name']
    assert seen['visibleWindowCount'] == counts[processes[case['name']]], (i, seen, counts)
failures = {
    'focus-en': 'English focus question still classified mixed and answered in Spanish.',
    'reference-new-name-en': 'Unnecessary clarification loses the preceding window-status question.',
    'reference-pronoun-en': 'Spotify reference is lost and the answer reports an interpretation failure.',
    'reference-new-name-es': 'Steam follow-up is falsely presented as unsupported.',
    'reference-pronoun-es': 'Application reference is lost; clarification unnecessarily changes the scope to an app in startup.',
}
judged = [{**case, 'terminal': final, 'observation': observations.get(f't{i}'),
           'verdict': 'failed' if case['case_id'] in failures else 'correct',
           'reason': failures.get(case['case_id'], 'Preserves requested scope, observed state/count, and language.')}
          for i, (case, final) in enumerate(zip(panel, finals), 1)]
write(private/'adjudication.json', judged)
report = ['# Producto 642 — 15 de 20 acreditados']
for r in judged:
    report += ['## '+r['case_id'], r['text'], r['terminal']['final'],
               r['verdict']+': '+r['reason'], json.dumps(r['observation'], ensure_ascii=False)]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n', encoding='utf-8', newline='\n')
note = '''# Fuente 641 / producto 642 — cantidad inglesa con lectura nueva

Se conserva el acto de consulta de cantidad contra nombres del catálogo autenticado, sin ampliar `how` a cualquier petición. Los controles de explicaciones, cantidades de ventanas cerradas, ventanas físicas, otro dispositivo y peticiones compuestas mantienen su frontera. No cambia el modelo, su perfil, el compositor ni el provider.

642 repite exactamente los 20 casos de 640: 15 acreditados frente a 14. «How many windows of Steam are open?» ahora ejecuta `window.application.status`, observa dos ventanas y responde «Two Windows of Steam are open.». La mayúscula de Windows es una imperfección tipográfica; no cambia el referente ni el número. Las doce lecturas explícitas por nombre/cantidad coinciden con instantáneas Win32 idénticas antes y después. Persisten cuatro fallos de referencia y el idioma español ante la pregunta inglesa sobre el foco; H0040 sigue abierto. Encuesta: 25 cubiertos, 717 abiertos, 0 no aplicables.

Validación: 16 rojos iniciales → 72 focales verdes; 3455 pruebas dueñas y 121 subpruebas, sin omisiones (67,64 s). Declaraciones del árbol: 12 pass y 1 skip ambiental (1,44 s), separado de los pases. Fast exit 0; Release 24,68 s, cero advertencias y errores. Full 630 sigue siendo la línea base anterior, no un Full de 641 ni un cierre C03.

Recursos 642: GPU 3497,559 MiB, RAM 2400,695 MiB, duración 59,297 s, sin infracciones. Registro y fuentes permanecieron intactos durante la prueba. Estos datos corresponden al conductor, sin crédito de interfaz ni voz simultáneas; no son el mínimo global de BAXY.

Próxima frontera: 640 muestra que `window.application.status` falta en las candidatas de «And Spotify?» y «¿Y Steam?». El modelo sí recibe la historia con sus roles originales; la pérdida ocurre antes, al recuperar con el texto actual solamente. Investigar candidatos contextuales acotados, sin convertir peticiones anteriores en autorización. `¿Esa aplicación…?` sí propone la operación y pierde el referente después: defecto distinto, aún sin reparar.
'''
seal(out, private, {'source': 641, 'correct': 15, 'total': 20, 'failed_cases': failures,
     'english_count_fresh_typed_read': True, 'explicit_named_reads_correct': 12,
     'independent_snapshots_identical': True, 'resources': read(out/'resources.json'),
     'ui_or_voice_credit': False, 'whole_window_requirement_accepted': False}, note,
     ['panel.json', 'capture/events.jsonl', 'compose-audit.jsonl', 'turn-audit.jsonl',
      'raw-replies.jsonl', 'shell-trace.jsonl', 'adjudication.json', 'RESULT.md',
      'windows-before.json', 'windows-after.json'])
out = base/'astra-count-source641'; prereg = read(out/'PREREG.json')
assert not (out/'RESULT.json').exists()
assert all(sha(root/p) == value for p, value in prereg['sources'].items())
for original, target in [('c03-count641-fast.log', 'FAST.log'), ('c03-count641-pins.log', 'DECLARATIONS.log')]:
    (out/target).write_bytes((Path(os.environ['TEMP'])/original).read_bytes())
write(out/'RESULT.json', {'adopted': True, 'owners_passed': 3455, 'subtests': 121,
     'owners_skipped': 0, 'targeted_passed': 72, 'declarations_passed': 12,
     'declarations_environmental_skipped': 1, 'fast_exit': 0, 'release_seconds': 24.68,
     'product642_correct': 15, 'product642_total': 20, 'goal_complete': False})
(out/'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out/'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root/'.gitattributes').open('a', encoding='utf-8', newline='\n') as f:
    f.write('/artifacts/comprobaciones/C03/astra-count-source641/** -text\n')
state = read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='641 validada: 3455 dueñas +121 subpruebas /0 skips, Fast. 642:15/20 con nueva lectura inglesa. 25/717/0.',
    continuation='Publicar 641–642. Después medir candidatos contextuales para seguimientos: shortlist actual no incluye window.application.status en t15/t17. No reescribir historia como mandato ni cambiar composición. Referente de argumentos t18 y detección de idioma has son fronteras separadas. UI/voz/recuperación/encuesta/Full final siguen pendientes.',
    publishedSourceCommit='pending_publication_of_validated_source641',
    previousGoalTurnClassification='progress',
    previousGoalTurnClassificationReason='Fresh English quantity read verified in product642; owners and Fast pass.',
    pendingOwnerClarification=None)
write(base/'RELEVO_ACTIVO.json', state)
(base/'HANDOFF.md').write_text('# Handoff C03 — 641 validada, publicación pendiente\n\n'+note,
    encoding='utf-8', newline='\n')
print({'source': 641, 'product642_correct': 15, 'total': 20, 'goal_complete': False})
