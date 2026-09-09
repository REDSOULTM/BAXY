"""Seal all outcomes and adopt the verified fresh-read interpretation repair."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
helper = (root / 'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(helper[:helper.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base / 'astra-survey-focus684'
private = home / 'C03-survey-focus684-private'
assert not (out / 'RESULT.json').exists()
assert read(out / 'EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
prereg = read(out / 'PREREG.json')
assert all(sha(root / name) == expected for name, expected in prereg['sources'].items())
panel = read(private / 'panel.json')
assert panel == read(home / 'C03-survey-focus681-private/panel.json')
events = rows(private / 'capture/events.jsonl')
finals = [r for r in events if r.get('type') == 'terminal']
decisions = [r for r in rows(private / 'turn-audit.jsonl') if r['phase'] == 'final']
compose = rows(private / 'compose-audit.jsonl')
assert len(panel) == len(finals) == len(decisions) == 7
snapshots = [read(private / f'foreground-{when}.json') for when in ['before', 'after']]
assert all(snapshots[0][key] == snapshots[1][key] for key in ['handle', 'title', 'pid', 'state', 'process'])
adjudication = []
for index, (case, final, decision) in enumerate(zip(panel, finals, decisions), 1):
    assert decision['decision_path'] == 'explicit_effects'
    assert decision['raw_decision']['operation'] == 'window.active'
    draft = next(r for r in compose if r.get('trace') == f't{index}' and r.get('stage') == 'first')
    payload = draft['payload']
    assert payload['operation'] == 'window.active'
    window = payload['seen']['windows'][0]
    assert window['is_current_window_for_user_interaction'] is True
    assert window['title'] == snapshots[0]['title'] and window['state'] == snapshots[0]['state']
    failed = index in [3, 4, 5]
    assert final['kind'] == ('composition_failed' if failed else 'published_final') and not final['timedOut']
    adjudication.append({**case, 'terminal': final, 'decision': decision, 'first_draft': draft,
        'fresh_read': True, 'verdict': 'failed' if failed else 'correct',
        'reason': 'Fresh, verified foreground read and truthful natural final.' if not failed else
        'Fresh read is correct, but the valid identity/focus wording is rejected as missing_fact; no useful final. Current title differs from679/681, so lexical changes are not attributed to source683.'})
activity = [r['event']['entry']['msg'] for r in events if r.get('type') == 'event'
    and r['event'].get('type') == 'activity' and r['event']['entry']['src'] == 'BAXY']
assert activity == [r['final'] for r in finals if r['kind'] == 'published_final']
write(private / 'adjudication.json', adjudication)
report = ['# Producto684: siete lecturas frescas; cuatro respuestas publicadas correctas']
for row in adjudication:
    report += ['## ' + row['case_id'], row['text'], row['terminal']['final'], row['reason'],
        json.dumps(row['first_draft'], ensure_ascii=False), json.dumps(row['decision'], ensure_ascii=False)]
(private / 'RESULT.md').write_text('\n\n'.join(report) + '\n', encoding='utf-8', newline='\n')
note = '''# 684 — siete consultas vuelven a leer Windows; finales4/7

Mismo panel de siete consultas681, ahora con otro título de ventana real. Las siete pasan por explicit_effects/window.active y llevan observación verificada que coincide con el título/estado de snapshots independientes antes/después. t3/t5 ya no responden desde conversación: la reparación de alcance y referencia está confirmada. Cuatro finales correctos; t3/t4/t5 terminan en composition_failed porque el verificador no reconoce la forma de identificar la ventana o el sujeto pospuesto. Los borradores y las causas completas están en el informe privado.

No se atribuye a683 una reparación léxica: el nombre/título observado cambió y llm.py no cambió. Las cuatro actividades coinciden con finales; ningún fallo cuenta como pase ni como lectura ausente. GPU3497,559MiB/RAM2363,301MiB/56,140s sin infracciones. Capturas antes/después no son observación continua; sin UI/voz conjunta. Encuesta26cubiertos/716abiertos/0NA, H0104abierto.
'''
seal(out, private, {'source': 683, 'fresh_reads': 7, 'correct': 4, 'total': 7,
    'failed_cases': ['focus-order-es', 'focus-mixed', 'focus-reference-es'],
    'all_decisions_explicit_window_active': True, 'same_panel681': True,
    'resources': read(out / 'resources.json'), 'ui_or_voice_credit': False,
    'visible_activity_matches_finals': True, 'goal_complete': False}, note,
    ['panel.json', 'capture/events.jsonl', 'compose-audit.jsonl', 'turn-audit.jsonl',
     'foreground-before.json', 'foreground-after.json', 'adjudication.json', 'RESULT.md'])

out = base / 'astra-native-paraphrase685'
private = home / 'C03-native-paraphrase685-private'
assert not (out / 'RESULT.json').exists()
panel = {(r['case_id'], r['arm']): r for r in read(private / 'panel.json')}
responses = rows(private / 'responses.jsonl')
old = {(r['case_id'], r['arm']): r for r in rows(home / 'C03-native-mixed-focus682-private/responses.jsonl')}
assert len(responses) == len(panel) == 10
adjudication = []
for row in responses:
    choice = row['response']['choices'][0]
    assert choice['finish_reason'] == 'stop'
    draft = choice['message']['content']
    if row['arm'] == 'compositor_control':
        assert draft == old[row['case_id'], 'compositor']['response']['choices'][0]['message']['content']
    failed = 'ventanal' in draft
    adjudication.append({**panel[row['case_id'], row['arm']], 'draft': draft,
        'verdict': 'failed' if failed else 'correct', 'reason':
        'Architectural noun incorrectly describes a software window.' if failed else
        'Individually reviewed correct observed window identity and natural ES/EN/mixed wording.'})
counts = {arm: sum(r['arm'] == arm and r['verdict'] == 'correct' for r in adjudication)
          for arm in ['compositor_control', 'without_paraphrase']}
assert counts == {'compositor_control': 3, 'without_paraphrase': 4}
write(private / 'adjudication.json', adjudication)
report = ['# 685: una mejora, defecto léxico restante; sin adopción']
for row in adjudication:
    report += ['## ' + row['case_id'] + ' / ' + row['arm'], row['text'], row['draft'], row['reason']]
(private / 'RESULT.md').write_text('\n\n'.join(report) + '\n', encoding='utf-8', newline='\n')
note = '''# 685 — retirar la obligación de parafrasear no resuelve toda la cohorte

Diez primeras respuestas nativas; los cinco controles reproducen682 exactamente. Se quita sólo «Expresa el mensaje con tus propias palabras»: mejora3/5→4/5, corrigiendo el nombre original, pero Atlas sigue descrito como ventanal. Los tres controles restantes conservan una respuesta válida. La petición, datos, idioma, identidad, requisitos de verdad y perfil permanecen iguales. No se adopta una reparación del caso original como solución general ni se cambia llm.py.

10EOS, GPU3497,559MiB/RAM722,570MiB/4,922s, sin infracciones y manifiesto intacto. Diagnóstico nativo; no UI/voz/encuesta. Siguiente: reparar el contrato factual que rechaza respuestas identificadoras válidas de684; conservar esta hipótesis parcial y no repetir una retirada completa de instrucciones que ya produjo otras invenciones.
'''
seal(out, private, {'counts': counts, 'total_per_arm': 5, 'native_calls': 10, 'all_eos': True,
    'all_controls_reproduce682': True, 'source_adopted': False, 'resources': read(out / 'RESOURCES.json'),
    'goal_complete': False}, note, ['panel.json', 'requests.jsonl', 'responses.jsonl', 'adjudication.json', 'RESULT.md'])

out = base / 'astra-fresh-window-source683'
assert not (out / 'RESULT.json').exists()
prereg = read(out / 'PREREG.json')
assert all(sha(root / name) == expected for name, expected in prereg['sources'].items())
for suffix, name in [('owners', 'OWNERS'), ('declarations', 'DECLARATIONS'), ('fast', 'FAST')]:
    temp = Path(os.environ['TEMP'])
    assert (temp / f'c03-fresh-window683-{suffix}.exit.txt').read_text().strip() == '0'
    (out / (name + '.log')).write_bytes((temp / f'c03-fresh-window683-{suffix}.log').read_bytes())
assert '7682 passed' in (out / 'OWNERS.log').read_text(encoding='utf-8-sig')
assert '600 passed, 1 skipped' in (out / 'DECLARATIONS.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'FAST.log').read_text(encoding='utf-8-sig')
note = '''# 683 — lectura fresca de marcos temporales y referencias adoptada

El encabezado delimitado de tiempo presente se conserva como marco del pedido mediante _REQUEST_PREFIX. La rama contextual ya existente para lecturas de hora admite también una pregunta nominal de foco, sólo si el pedido inmediatamente anterior del usuario se resuelve independientemente y únicamente a window.active. No usa la prosa del asistente ni un estado viejo como evidencia; no hereda acciones, otro dominio o una petición compuesta. No añade dispatcher, modelo, respuesta visible fija ni cambios C#.

52casos nuevos:36fallos/16pases→52pases. Incluyen ES/EN/mezcla, prefijos, referentes, ausencia de catálogo, otra máquina/tiempo, negación, citas, cambio de tema y la tubería real de decisión con un transporte que impide sustituir la lectura por charla. Dueñas31archivos7682pases/0skips92,42s; declaraciones600pases/1skip ambiental3,98s por entradas ausentes de campaña ciega STT. Fast exit0/Release19,50s,0advertencias/errores. Producto684 confirma7/7lecturas frescas, pero sólo4/7finales: siguen falsos rechazos de redacción en el verificador. La referencia explícita aquí es de un salto; no se declara comprensión universal de cadenas elípticas.

Tree6c474bfe4350dd0203b70a509a39d816feda4b0bf85a9a620e43512e6ae23ae5/405archivos y declaraciones actuales actualizadas. Encuesta26/716/0 intacta; C03 EN_CURSO. Full651 sigue baseline, no Full683: otro Full al adoptar C#+Python juntos o candidato final. Durante una actualización auxiliar, RELEVO_ACTIVO quedó temporalmente null por una variable PowerShell equivocada; se restauró desde HEAD verificado y se reaplicó el progreso real antes de continuar. Fuente, encuesta y evidencias no se alteraron por ese incidente.
'''
seal(out, out, {'adopted': True, 'sources': prereg['sources'], 'python_tree_sha256': prereg['python_tree_sha256'],
    'baseline': {'failed': 36, 'passed': 16}, 'focal_passed': 52,
    'owners': {'files': 31, 'passed': 7682, 'skipped': 0, 'seconds': 92.42},
    'declarations': {'passed': 600, 'environmental_skipped': 1, 'seconds': 3.98},
    'fast_exit': 0, 'release_seconds': 19.50, 'product684_fresh_reads': 7,
    'product684_correct': 4, 'product684_total': 7, 'full683_run': False, 'full_baseline': 651,
    'goal_complete': False}, note, [])
state_path = base / 'RELEVO_ACTIVO.json'
state = read(state_path)
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='683 adoptada:7682dueñas/0skip;600declaraciones/1skip ambiental;Fast0.6847/7lecturas frescas,4/7finales;6853/5→4/5sin adopción.',
    continuation='Auditar y publicar683/684/685; luego reparar el rechazo de respuestas identificadoras e inversión de sujeto en window_prose_facts. Conservar las preguntas originales y contradicciones; no declarar cubierta H0104 todavía.',
    activeValidation=None, previousGoalTurnClassification='progress',
    previousGoalTurnClassificationReason='683 reparó las dos rutas que respondían desde historial; producto684 verifica siete lecturas frescas.685 aisló una cláusula de paráfrasis con mejora parcial y sin adopción.')
write(state_path, state)
handoff = '''# C03 — fuente683 adoptada; publicar antes de otra reparación

Goal activo en Goal-c03; main5f572ee1b48cb5e2543ee5e06510e51057c9c845 intacto. Objetivo C:/Users/usuario/.codex/attachments/b424eff2-0702-4cc9-871a-451d31ecf314/goal-objective.md. Sin agentes/decisión pendiente. Preservar otra tarea del dueño en VSCode. Fuente anterior680publicadae2ad0b5c, HEAD previo8c79def4. Ahora683adoptada y aún sin commit.

683 extiende el marco temporal presente delimitado y reutiliza la rama de lectura contextual de hora para foco nominal con único antecedente de usuario. Sóloeffect_intent.py; no nuevo dispatcher/LLM/C#.52nuevos36fail16pass→52pass; dueñas31archivos7682pass/0skip92,42s;600declaraciones/1skip ambiental3,98s;Fast0/Release19,50s. Tree6c474bfe4350dd0203b70a509a39d816feda4b0bf85a9a620e43512e6ae23ae5/405archivos. No Full683 por regla Python-only; Full651baseline, Full final pendiente.

684 mismo panel7: ahora7lecturas frescas, todasexplicit_effects/window.active, pero4finales. t3/t4/t5tienen payload correcto y borrador identificador correcto, rechazadosmissing_fact por window_prose_facts. El foco/título real cambió a otro programa; no atribuir variación léxica a683. Ver privados C03-survey-focus684-private/compose-audit.jsonl (sólo primeras filas de cada trace) y RESULT.md. t3usa«La ventana con enfoque es…»; t5«Ahora está activa la ventana de…titulada…». t4también tiene sujeto pospuesto. Snapshotsantes/despuéscoinciden, no continuos.

685diagnóstico nativo10EOS: retirar sólo«Expresa el mensaje con tus propias palabras»da3/5→4/5; originalChatGPTmejora, Atlas sigueventanal. No se adopta ni cambia llm.py. Cinco controles reproducen682exactamente. Mantener685cerrado, no repetir: es una mejora parcial, no solución general.

Siguiente tras publicación: distinguir respuesta de identidad («qué/cuál ventana») de Booleano («está Atlas activa») en la validación de cobertura, y comprobar contradicciones/inversión de sujeto con pruebas de nombres/valores. Evitar listas de frases de respuesta: el fallo es el tipo de respuesta exigida. Pregunta original de679yvariantes intactas. H0104abierto; encuesta742/rev1248:26cubiertos/716abiertos/0NA, SHA237c14900a9e36e2e5f6071f132ad916a234ecb39a77e0dd497ef2565eceb2b7.

683fuente/evidencia pública astra-fresh-window-source683; producto astra-survey-focus684; diagnóstico astra-native-paraphrase685. Scripts prepare683/product684/native685/close683-685 YA ejecutados. Sesiones63475/70980/20597 terminalesexit0;685 terminó en su llamada. BAXY cerrado, ninguna campaña activa.684GPU3497,559MiB/RAM2363,301MiB/56,140s;685RAM722,570MiB/4,922s. Sin UI/voz conjunta ni mínimo global. RAM libre tras cierre normal buildservers4262,5MiB antes684.

Runtime Qwen4B2507Q4_K_M/b9980,manifest13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed intacto. Python %LOCALAPPDATA%/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8; calidad por defectoBAXYQuality. No solapar pruebas/build/inferencia; no eludir bloqueoComputerUse de navegadores. RELEVO temporalmente null por error auxiliar fue restaurado desdeHEAD verificado y validado; fuente/encuesta/evidencias intactas.

C03completo sigue abierto: ocho rutas, encuesta/cien respuestas, UI real, loopback entero/AEC separado, avería→restauración→normal, recursos conjuntos y Full final. C08humano/wake/FARFRR sóloevidencia; continuidadC04–C09documentada, no ejecutar susgoals.
'''
(base / 'HANDOFF.md').write_text(handoff, encoding='utf-8', newline='\n')
print({'adopted': 683, 'product684_fresh_reads': '7/7', 'product684_final_correct': '4/7', 'diagnostic685': counts})
