"""Adopt the title repair, correct freshness scoring, and preserve native evidence."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
helper = (root / 'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(helper[:helper.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
strict = {}
for campaign in [679, 681]:
    private = home / f'C03-survey-focus{campaign}-private'
    panel = read(private / 'panel.json')
    events = rows(private / 'capture/events.jsonl')
    finals = [r for r in events if r.get('type') == 'terminal']
    decisions = [r for r in rows(private / 'turn-audit.jsonl') if r['phase'] == 'final']
    compose = rows(private / 'compose-audit.jsonl')
    observations = {r['trace']: r['payload'] for r in compose
        if r.get('published') and r.get('payload', {}).get('operation') == 'window.active'}
    assert len(panel) == len(finals) == len(decisions) == 7
    assert read(base / f'astra-survey-focus{campaign}/EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
    activity = [r['event']['entry']['msg'] for r in events if r.get('type') == 'event'
        and r['event'].get('type') == 'activity' and r['event']['entry']['src'] == 'BAXY']
    assert activity == [r['final'] for r in finals if r['kind'] == 'published_final']
    adjudication = []
    for index, (case, final, decision) in enumerate(zip(panel, finals, decisions), 1):
        observed = observations.get(f't{index}')
        fresh = observed is not None
        if index in [3, 5]:
            assert decision['raw_decision']['mode'] == 'conversation' and not fresh
        correct = final['kind'] == 'published_final' and fresh
        assert not final['timedOut']
        reason = ('Correct observed foreground identity and requested language; real window.active read.' if correct else
            'No new window read: the native decision classified the question as conversation. A coincidentally matching or stale remembered answer cannot satisfy the preregistered freshness criterion.' if index in [3, 5] else
            'Composition failed; mixed lexical defect remains.' if index == 4 else
            'Valid title-only draft was rejected as a missing Boolean focus answer.')
        adjudication.append({**case, 'terminal': final, 'fresh_read': fresh, 'observation': observed,
            'decision': decision, 'verdict': 'correct' if correct else 'failed', 'reason': reason})
    strict[campaign] = sum(r['verdict'] == 'correct' for r in adjudication)
    assert strict[campaign] == (3 if campaign == 679 else 4)
    write(private / 'adjudication-freshness.json', adjudication)
    report = [f'# Producto{campaign}: {strict[campaign]}/7 con lectura fresca exigida']
    for row in adjudication:
        report += ['## ' + row['case_id'], row['text'], row['terminal']['final'], row['reason'],
            json.dumps(row['observation'], ensure_ascii=False), json.dumps(row['decision'], ensure_ascii=False)]
    (private / 'RESULT-freshness.md').write_text('\n\n'.join(report) + '\n', encoding='utf-8', newline='\n')

out = base / 'astra-survey-focus681'
assert not (out / 'RESULT.json').exists()
private = home / 'C03-survey-focus681-private'
assert read(private / 'panel.json') == read(home / 'C03-survey-focus679-private/panel.json')
assert all(sha(root / name) == value for name, value in read(out / 'PREREG.json')['sources'].items())
note = '''# 681 — petición de nombre reparada; resultado estricto3/7→4/7

Se corrige explícitamente el recuento6795/7: eran cinco finales aparentemente correctos, pero t3/t5 carecían de una nueva lectura de ventana. El preregistro679 ya exigía window.active fresco. La adjudicación revisada da3/7 y se conserva junto a los originales sellados, sin reescribir sus bytes.681 alcanza4/7 bajo ese mismo criterio. No se relaja ni se sustituye la entrada: los siete casos y su orden son idénticos.

La petición del nombre pasa de composition_failed a «ChatGPT» en una llamada, con el mismo primer borrador y payload observado que679. El cambio sólo modifica la lectura de la relativa usada por la validación de cobertura. t4 sigue fallando por prosa mixta. t3/t5 ya se clasificaban como conversación en679, sin operación: en681 t3 pide aclaración innecesaria y t5 recuerda el Administrador de tareas aunque t4 ya observó ChatGPT. No es una regresión introducida por680: es el fallo previo de lectura fresca ahora expuesto con foco variable.

Antes y después del panel el snapshot independiente muestra ChatGPT. Durante t2, el provider observa Administrador de tareas; no se atribuye a las capturas antes/después una observación continua. Las seis actividades publicadas coinciden con sus terminales, incluidas la aclaración y la respuesta histórica incorrectas; la emisión no equivale a aceptación. GPU3497,559MiB/RAM2387,883MiB/48,594s sin infracciones. Sin UI/voz conjunta. Encuesta26cubiertos/716abiertos/0NA; H0104 permanece abierto.
'''
seal(out, private, {'correct': 4, 'total': 7, 'corrected679_correct': 3, 'previous679_reported': 5,
    'failed_cases': ['focus-order-es', 'focus-mixed', 'focus-reference-es'],
    'title_repaired_with_identical_first_draft': True, 'same_panel': True,
    'resources': read(out / 'resources.json'), 'visible_activity_matches_terminals': True,
    'ui_or_voice_credit': False, 'corrected679_private_hashes': {
        name: sha(home / 'C03-survey-focus679-private' / name)
        for name in ['adjudication-freshness.json', 'RESULT-freshness.md']}, 'goal_complete': False}, note,
    ['panel.json', 'capture/events.jsonl', 'compose-audit.jsonl', 'turn-audit.jsonl',
     'foreground-before.json', 'foreground-after.json', 'adjudication-freshness.json', 'RESULT-freshness.md'])

out = base / 'astra-native-mixed-focus682'
private = home / 'C03-native-mixed-focus682-private'
assert not (out / 'RESULT.json').exists()
responses = rows(private / 'responses.jsonl')
assert len(responses) == 15 and all(r['response']['choices'][0]['finish_reason'] == 'stop' for r in responses)
by_key = {(r['case_id'], r['arm']): r['response']['choices'][0]['message']['content'] for r in responses}
assert by_key['mixed-original', 'compositor'] == 'Ahora tiene focus el ventanal de ChatGPT.'
assert by_key['mixed-original', 'identity_facts'] == 'ChatGPT'
assert 'ventanal' in by_key['mixed-other-name', 'compositor']
panel = {(r['case_id'], r['arm']): r for r in read(private / 'panel.json')}
adjudication = []
for row in responses:
    case = panel[row['case_id'], row['arm']]
    draft = row['response']['choices'][0]['message']['content']
    failed = row['arm'] == 'native_facts' and row['case_id'] != 'english-control'
    failed |= row['arm'] == 'compositor' and row['case_id'] in {'mixed-original', 'mixed-other-name'}
    reason = ('Natural current-window identity in the requested language; mixed input permits natural mixed wording.' if not failed else
        'Uses architectural noun ventanal for a software window.' if 'ventanal' in draft else
        'Native draft asserts the foreground observation is the only visible window or exposes internal schema instead of a natural answer; neither earns product-quality credit.')
    adjudication.append({**case, 'draft': draft, 'verdict': 'failed' if failed else 'correct', 'reason': reason})
write(private / 'adjudication.json', adjudication)
report = ['# 682 — el compositor reproduce el término impropio']
for row in adjudication:
    report += ['## ' + row['case_id'] + ' / ' + row['arm'], row['text'], row['draft'], row['reason'], json.dumps(row['facts'], ensure_ascii=False)]
(private / 'RESULT.md').write_text('\n\n'.join(report) + '\n', encoding='utf-8', newline='\n')
counts = {arm: sum(r['verdict'] == 'correct' and r['arm'] == arm for r in adjudication)
          for arm in ['native_facts', 'identity_facts', 'compositor']}
assert counts == {'native_facts': 1, 'identity_facts': 5, 'compositor': 3}
note = '''# 682 — la prosa mixta falla al aplicar el compositor completo

Cinco casos por tres variantes de instrucciones,15EOS. La petición mixta original reproduce exactamente «Ahora tiene focus el ventanal de ChatGPT» en el primer borrador del compositor real; el mismo defecto aparece con Atlas y desaparece con Órbita29. Con identidad y hechos,5/5respuestas aceptables; compositor3/5; hechos solos1/5 por afirmaciones de única ventana visible no respaldadas por una observación de foco o por exposición de metadatos. Se conservan todos los borradores, no sólo el original favorable.

GPU3497,559MiB/RAM723,281MiB/20,140s sin infracciones; registro y perfiles iguales. Es un diagnóstico nativo, no otro producto, promoción de modelo ni prueba de ahorro conjunto. Quitar todas las instrucciones no es solución: la variante sin ellas introduce otros defectos. Próximo: aislar el contrato de prosa que induce la palabra impropia y reparar la lectura fresca de t3/t5 en su módulo dueño; no aceptar un texto sólo porque menciona el título correcto.
'''
seal(out, private, {'counts': counts, 'total_per_arm': 5, 'native_calls': 15,
    'all_eos': True, 'original_compositor_reproduces679': True, 'model_promoted': False,
    'resources': read(out / 'RESOURCES.json'), 'goal_complete': False}, note,
    ['panel.json', 'requests.jsonl', 'responses.jsonl', 'adjudication.json', 'RESULT.md'])

out = base / 'astra-focus-subject-source680'
assert not (out / 'RESULT.json').exists()
prereg = read(out / 'PREREG.json')
assert all(sha(root / name) == value for name, value in prereg['sources'].items())
for suffix, name in [('owners', 'OWNERS'), ('declarations', 'DECLARATIONS'), ('fast', 'FAST')]:
    assert (Path(os.environ['TEMP']) / f'c03-focus-subject680-{suffix}.exit.txt').read_text().strip() == '0'
    (out / (name + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-focus-subject680-{suffix}.log').read_bytes())
assert '2589 passed, 121 subtests passed' in (out / 'OWNERS.log').read_text(encoding='utf-8-sig')
assert '600 passed, 1 skipped' in (out / 'DECLARATIONS.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'FAST.log').read_text(encoding='utf-8-sig')
note = '''# 680 — alcance de relativas adoptado, sin cambio de modelo

La validación de cobertura distingue identificar una ventana («el nombre de la ventana que está en primer plano») de preguntar si está activa. Conserva el predicado principal en preguntas con relativas y mantiene el rechazo de contradicciones. Sólo10líneas en window_prose_facts; no cambio de primer prompt, borrador, reintentos, backend ni respuesta fija.23casos nuevos:9fallos/14pases antes→23pases. Focal344pases; dueñas24archivos2589pases+121subpruebas/0skips24,13s. Declaraciones600pases/1skip ambiental4,96s por campaña ciega STT ausente. Fast exit0,Release25,37s,0advertencias/errores.

Producto681 demuestra el nombre reparado en una llamada y conserva pendientes el caso mixto y las dos lecturas frescas omitidas. Recuento estricto6793/7→6814/7; el5/7anterior omitía el requisito de lectura fresca y queda corregido explícitamente en681. Encuesta26cubiertos/716abiertos/0NA intacta. El primer intento del script de preparación encontró una fila diagnóstica sin trace; se corrigió su acceso opcional antes de sellar679, sin repetir inferencia ni alterar fuente por ello.

Python tree03d2cb9ef539220225bb0efff7fc499cd2707466cf98fb1160d899b5a0ba67d7/405archivos, declaraciones actuales actualizadas y sellos históricos intactos. No Full680: Full651 sigue baseline; otro Full al adoptar C#+Python juntos o candidato final según el encargo. C03 no completo: ocho rutas, encuesta, cien respuestas, UI real, loopback íntegro/AEC separado, recuperación y recursos conjuntos/Full final siguen pendientes.
'''
seal(out, out, {'adopted': True, 'sources': prereg['sources'], 'python_tree_sha256': prereg['python_tree_sha256'],
    'baseline': {'failed': 9, 'passed': 14}, 'new_tests': 23, 'focal_passed': 344,
    'owners': {'files': 24, 'passed': 2589, 'subtests': 121, 'skipped': 0, 'seconds': 24.13},
    'declarations': {'passed': 600, 'environmental_skipped': 1, 'seconds': 4.96},
    'fast_exit': 0, 'release_seconds': 25.37, 'product681_correct': 4, 'product681_total': 7,
    'full680_run': False, 'full_baseline': 651, 'goal_complete': False}, note, [])
state_path = base / 'RELEVO_ACTIVO.json'
state = read(state_path)
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='680 adoptada: nombre de ventana reparado;2589dueñas+121subtests/0skips,600declaraciones/1skip ambiental,Fast0.679 corregido3/7;6814/7;682 diagnóstico nativo completo.',
    continuation='Auditar y publicar680 con evidencias679/681/682; luego reparar t3/t5: el clasificador nativo los trata como conversación sin lectura fresca. Prosa mixta localizada en compositor completo682. Sin nueva encuesta ni cambio de modelo.',
    activeValidation=None, previousGoalTurnClassification='progress',
    previousGoalTurnClassificationReason='Reparación680 validada y producto confirma título; auditoría descubre y corrige sobrecrédito679 por lecturas no realizadas.682 localiza defecto léxico sin cambiar backend.')
write(state_path, state)
handoff = '''# C03 — fuente680 adoptada; publicación pendiente

Goal activo en Goal-c03; main intacto5f572ee1b48cb5e2543ee5e06510e51057c9c845. Autoridad C:/Users/usuario/.codex/attachments/b424eff2-0702-4cc9-871a-451d31ecf314/goal-objective.md. Sin agentes ni decisión del dueño pendiente. Preservar la tarea de Claude en VS Code. Fuente anterior publicada2138d2d6; HEAD previo a680d7776f8e.

680 corrige únicamente el alcance de relativas en window_prose_facts.py.23nuevos:9fail14pass→23pass; focal344; dueñas24archivos2589pass+121subtests/0skip24,13s; declaraciones600pass/1skip ambiental4,96s; Fast0/Release25,37s. No Full680 bajo regla Python-only; Full651 baseline, Full final pendiente. Pins en astra-focus-subject-source680/RESULT.json. Tree03d2cb9ef539220225bb0efff7fc499cd2707466cf98fb1160d899b5a0ba67d7/405archivos.

679 inicialmente se informó5/7pero t3/t5 respondían sin leer Windows.681 audita y corrige explícitamente679a3/7, conservando sus sellos.6814/7: t6nombre ya publicaChatGPT con mismo primer borrador y payload; t4mixto siguecomposition_failed; t3consulta de foco pasa de conversación a aclaración innecesaria; t5recuerdaTaskmgrcuando t4ya observóChatGPT. t3/t5 son fallos previos de clasificación nativa conversation, no regresión de680. Encuesta742/rev1248:26cubiertos/716abiertos/0NA, H0104abierto. Hash237c14900a9e36e2e5f6071f132ad916a234ecb39a77e0dd497ef2565eceb2b7.

68215EOS/5casos×3: hechos solos1/5, identidad+hechos5/5, compositor3/5. Reproduce ventanal enChatGPTyAtlas; Órbita29responde sin ese defecto. No eliminar todo el contrato: hechos solos inventan única ventana visible o exponen esquema. Fuente/modelo sin cambios. Siguiente tras publicación: reparar lectura fresca de «Ahora mismo, ¿qué ventana tiene el foco?» y «¿Y ahora cuál está activa?» usando turn-audit.jsonl/compose-audit.jsonl679/681. Luego aislar instrucción del compositor que induce el término impropio;682respuestas completas guardadas.

Privados %LOCALAPPDATA%/BAXY/C03-survey-focus679-private, C03-survey-focus681-private, C03-native-mixed-focus682-private. Revisiones nuevas adjudication-freshness.json/RESULT-freshness.md preservan originales. Públicos astra-survey-focus679, astra-survey-focus681, astra-native-mixed-focus682.681GPU3497,559MiB/RAM2387,883MiB/48,594s;682RAM723,281MiB/20,140s. Sin UI/voz ni mínimo conjunto. Capturas antes/después no acreditan foco continuo.

BAXY manual cerrado; ninguna campaña activa. Sesiones41718/77948/65845/26488 terminalesexit0. Build servers cerrados antes681 y RAM libre3402MiB. Runtime Qwen4B2507Q4_K_M/b9980 manifest13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed intacto. Python %LOCALAPPDATA%/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8; calidad scripts/test_source_quality.ps1 por defecto BAXYQuality. No solapar inferencia/build/Full ni eludir bloqueo ComputerUse sobre navegadores.

Prepare680, product679/681, native682 y close680-682 ya ejecutados: no repetir. Restan alcance completo deC03: ocho rutas, encuesta/cien respuestas, UI real, loopback completo/AEC separado, avería→restauración→normal, recursos conjuntos y Full final. Voz humana/wake/FARFRRownerC08; continuidadC04–C09 documentada, no ejecutar sus goals.
'''
(base / 'HANDOFF.md').write_text(handoff, encoding='utf-8', newline='\n')
print({'adopted': 680, 'corrected679': '3/7', 'product681': '4/7', 'native682': counts, 'survey': '26/716/0'})
