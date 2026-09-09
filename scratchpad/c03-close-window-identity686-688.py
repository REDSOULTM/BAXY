"""Preserve all product outcomes and adopt the validated identity coverage correction."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
helper = (root / 'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(helper[:helper.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))

out = base / 'astra-survey-focus687'
private = home / 'C03-survey-focus687-private'
assert not (out / 'RESULT.json').exists()
assert read(out / 'EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
panel = read(private / 'panel.json')
assert panel == read(home / 'C03-survey-focus684-private/panel.json')
assert all(sha(root / n) == h for n,h in read(out / 'PREREG.json')['sources'].items())
events = rows(private / 'capture/events.jsonl')
finals = [r for r in events if r.get('type') == 'terminal']
decisions = [r for r in rows(private / 'turn-audit.jsonl') if r['phase'] == 'final']
compose = rows(private / 'compose-audit.jsonl')
snapshots = [read(private / f'foreground-{when}.json') for when in ['before','after']]
assert all(snapshots[0][k] == snapshots[1][k] for k in ['handle','title','pid','state','process'])
assert len(panel) == len(finals) == len(decisions) == 7
adjudication = []
for i,(case,final,decision) in enumerate(zip(panel,finals,decisions),1):
    draft = next(r for r in compose if r.get('trace') == f't{i}' and r.get('stage') == 'first')
    assert decision['decision_path'] == 'explicit_effects' and decision['raw_decision']['operation'] == 'window.active'
    window = draft['payload']['seen']['windows'][0]
    assert window['is_current_window_for_user_interaction'] is True
    assert window['title'] == snapshots[0]['title'] and window['state'] == snapshots[0]['state']
    failed = case['case_id'] == 'focus-mixed'
    assert final['kind'] == ('composition_failed' if failed else 'published_final') and not final['timedOut']
    adjudication.append({**case, 'terminal':final, 'decision':decision, 'first_draft':draft,
        'fresh_read':True, 'verdict':'failed' if failed else 'correct', 'reason':
        'Fresh verified foreground read and manually reviewed correct identity and language.' if not failed else
        'The first draft correctly identifies the observed title through a descriptive subject plus con el titulo; missing_fact rejects that relation. Third draft also has el ventana agreement error. No final, no credit; do not fix by accepting arbitrary mentions.'})
activity = [r['event']['entry']['msg'] for r in events if r.get('type') == 'event' and r['event'].get('type') == 'activity' and r['event']['entry']['src'] == 'BAXY']
assert activity == [r['final'] for r in finals if r['kind'] == 'published_final']
write(private / 'adjudication.json', adjudication)
report = ['# Producto687: seis respuestas correctas, siete lecturas frescas']
for r in adjudication:
    report += ['## '+r['case_id'], r['text'], r['terminal']['final'], r['reason'], json.dumps(r['first_draft'],ensure_ascii=False)]
report += ['## Borradores del fallo restante', *[json.dumps(r,ensure_ascii=False) for r in compose if r.get('trace') == 't4']]
(private / 'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note = '''# 687 — siete lecturas frescas y seis respuestas correctas

El mismo panel684 pasa de4/7 a6/7 finales correctos. t3 y t5 ya publican la identidad; las siete decisiones ejecutan window.active y sus observaciones coinciden con snapshots independientes antes/después. El título real cambió al Explorador: no se atribuye al cambio una mejora léxica. t4 sigue fallando: su primer borrador correcto usa un sujeto descriptivo seguido de «con el título», relación que el verificador no reconoce. Su tercer borrador además tiene un error de concordancia. Todos los intentos y el fallo final se conservan; H0104 sigue abierto.

Seis actividades coinciden con los finales; sin timeout. GPU3497,559MiB/RAM2286,984MiB/31,672s, sin infracciones. No prueba de UI/voz simultáneas ni mínimo global. Encuesta26cubiertos/716abiertos/0NA. El dueño pide desde ahora tandas de50 entradas o categorías completas: el caso pendiente se integra en la siguiente tanda de consultas de estado, conservando su criterio individual.
'''
seal(out,private,{'source':686,'fresh_reads':7,'correct':6,'total':7,'failed_cases':['focus-mixed'],
    'resources':read(out/'resources.json'),'same_panel684':True,'visible_activity_matches_finals':True,
    'ui_or_voice_credit':False,'goal_complete':False},note,
    ['panel.json','capture/events.jsonl','compose-audit.jsonl','turn-audit.jsonl','foreground-before.json','foreground-after.json','adjudication.json','RESULT.md'])

out = base / 'astra-compositor-window-identity688'
private = home / 'C03-compositor-window-identity688-private'
assert not (out / 'RESULT.json').exists()
panel = read(private / 'panel.json')
finals = rows(private / 'finals.jsonl')
old = {r['case_id']:r for r in rows(home/'C03-compositor-focus-coverage677-private/finals.jsonl')}
requests = rows(private/'requests.jsonl')
responses = rows(private/'responses.jsonl')
old_requests = {(r['case_id'],r['call']):r['payload'] for r in rows(home/'C03-compositor-focus-coverage677-private/requests.jsonl')}
assert len(finals) == len(panel) == 17 and len(responses) == 24
assert all(r['response']['choices'][0]['finish_reason'] == 'stop' for r in responses)
assert all(r['payload'] == old_requests[r['case_id'],r['call']] for r in requests)
assert all(r['final'] == old[r['case_id']]['final'] and r['calls'] == old[r['case_id']]['calls'] for r in finals)
resources = read(out/'RESOURCES.json')
assert resources['complete'] and resources['manifest_unchanged'] and not resources['violations']
adjudication = [{**case, 'result':r, 'verdict':'correct', 'reason':'Individually reviewed; same final and requests as677. Focus and always-on-top retain their separate Boolean values; identity/state/count match the fixture.'} for case,r in zip(panel,finals)]
write(private/'adjudication.json',adjudication)
report = ['# Compositor688: 17/17; regresión exacta677']
for r in adjudication:
    report += ['## '+r['case_id'],r['text'],r['result']['final'],r['reason'],json.dumps(r['facts'],ensure_ascii=False)]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note = '''# 688 — regresión integrada17/17 conservada

Mismos17casos677 y mismas24 peticiones nativas: diez controles en una llamada, siete preguntas compuestas en dos. Los17finales también son idénticos y correctos, con foco y siempre encima separados. Todas24terminaciones EOS. GPU3497,559MiB/RAM720,297MiB/11,328s, sin infracciones ni cambios de registro. Es compositor real con transporte local, sin kernel/UI/voz. No añade cobertura de encuesta por sí solo.
'''
seal(out,private,{'correct':17,'total':17,'native_calls':24,'all_requests_and_finals_same677':True,
    'resources':resources,'goal_complete':False},note,['panel.json','requests.jsonl','responses.jsonl','finals.jsonl','adjudication.json','RESULT.md'])

out = base/'astra-window-identity-source686'
assert not (out/'RESULT.json').exists()
prereg = read(out/'PREREG.json')
assert all(sha(root/n)==h for n,h in prereg['sources'].items())
for suffix,name in [('owners','OWNERS'),('declarations','DECLARATIONS'),('fast','FAST')]:
    temp = Path(os.environ['TEMP'])
    assert (temp/f'c03-window-identity686-{suffix}.exit.txt').read_text().strip() == '0'
    (out/(name+'.log')).write_bytes((temp/f'c03-window-identity686-{suffix}.log').read_bytes())
assert '2712 passed, 121 subtests passed' in (out/'OWNERS.log').read_text(encoding='utf-8-sig')
assert '12 passed, 1 skipped' in (out/'DECLARATIONS.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out/'FAST.log').read_text(encoding='utf-8-sig')
note = '''# 686 — distinción de identidad y estado adoptada

El contrato factual diferencia el nombre pedido de la confirmación Booleana. Liga sujetos nominales o pospuestos a nombres observados únicos y mantiene los títulos citados como identificadores opacos, incluso con puntuación o nombres como «Is Active». Conserva contradicciones, incertidumbre y predicados compuestos. No cambia el modelo, primer prompt, backend, dispatcher ni texto visible fijo. Es gramática delimitada, sin afirmación de verificación semántica universal.

71casos nuevos: baseline publicada683 aislada50fallos/21pases; focal415pases. Se conservan baseline inicial35fallos/18pases y regresión intermedia de nombres con punto8fallos/63pases. Un test antiguo que confundía identidad con respuesta sin nombre ahora pregunta por el Booleano; los nuevos controles exigen identidad en preguntas WH. Dueñas26archivos2712pases+121subpruebas/0skips24,70s; las declaraciones dueñas actuales12pases/1skip ambiental1,18s por entradas ausentes de campaña ciega STT (no se declara repetida la cohorte histórica600). Fast exit0/Release20,72s,0advertencias/errores.

Producto6876/7 con siete lecturas frescas; compositor68817/17 conserva peticiones y finales677. Se adopta la reparación comprobada y se conserva el fallo descriptivo de t4 como pendiente, sin dar por cubierta H0104. Árbol Python50f0fb6bf6bd81210a800b72be09bf2a9544c7b9e482a54629c2141344ca1439/405archivos. Full651 sigue baseline: no Full por edición Python, Full final aún requerido. Encuesta26/716/0; C03 EN_CURSO. Siguiente tanda50 de estado del PC por dirección expresa del dueño, con adjudicación individual y variantes compartidas por conducta.
'''
seal(out,out,{'adopted':True,'sources':prereg['sources'],'python_tree_sha256':prereg['python_tree_sha256'],
    'baseline':{'failed':50,'passed':21},'focal_passed':415,
    'owners':{'files':26,'passed':2712,'subtests':121,'skipped':0,'seconds':24.70},
    'declarations':{'passed':12,'environmental_skipped':1,'seconds':1.18},'fast_exit':0,'release_seconds':20.72,
    'product687_correct':6,'product687_total':7,'compositor688_correct':17,'full686_run':False,'full_baseline':651,'goal_complete':False},note,[])
state_path = base/'RELEVO_ACTIVO.json'
state = read(state_path)
assert state['threadId'] == '01a07974-2a33-7ed3-ba87-2436944e8115'
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='686adoptada:2712dueñas+121subpruebas,12declaraciones/1skip ambiental,Fast0;6876/7;68817/17. Publicación siguiente.',
    continuation='Publicar686–688; ejecutar tanda689 de50 consultas de estado del PC con variantes y criterio individual. Mantener fallo descriptivo de foco687 en la tanda; encuesta26/716/0.',
    activeValidation=None,previousGoalTurnClassification='progress',previousGoalTurnClassificationReason='RAM liberada y candidato686 validado; producto687 mejora4/7→6/7 sin perder regresión17/17. Dueño cambia unidad de trabajo a tandas50/categorías.')
write(state_path,state)
matrix = root/'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
lines = matrix.read_text(encoding='utf-8-sig').splitlines()
for i,line in enumerate(lines):
    if line.startswith('| G04.02 /') or line.startswith('| G06.01 /'):
        assert line.endswith('|')
        lines[i]=line[:-1]+' Fuente686: identidad/estado distinguido;2712dueñas+121subpruebas,Fast0. [Producto687](../../../artifacts/comprobaciones/C03/astra-survey-focus687/RESULT.md)6/7 con siete lecturas frescas; [compositor688](../../../artifacts/comprobaciones/C03/astra-compositor-window-identity688/RESULT.md)17/17. Falso rechazo descriptivo restante, encuesta26/716/0 y C03global abiertos. |'
matrix.write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
print({'adopted686':True,'product687':'6/7','regression688':'17/17','survey':'26/716/0'})
