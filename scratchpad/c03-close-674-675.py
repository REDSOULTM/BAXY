"""Preserve integrated feedback and the two remaining incomplete answers."""
from pathlib import Path
import subprocess
root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base / 'astra-focus-feedback-source674'
out.mkdir(exist_ok=False)
(out/'CANDIDATE.patch').write_bytes(subprocess.check_output(['git','diff','--','src/baxy_mind/llm.py','src/baxy_mind/window_prose_facts.py'], cwd=root))
(out/'CANDIDATE_TEST.py').write_bytes((root/'tests/test_c03_window_state_facts.py').read_bytes())
(out/'FOCAL.log').write_bytes((Path(os.environ['TEMP'])/'c03-state-feedback674-focal.log').read_bytes())
assert '669 passed' in (out/'FOCAL.log').read_text(encoding='utf-8-sig')
note674='''# 674 — información verificada en el reintento existente

El contrato factual ahora devuelve la contradicción concreta, derivada del título y foco observado, conservando valor observado, valor afirmado y borrador. El compositor lleva esos datos JSON en su mensaje de usuario del reintento; no cambia instrucciones de sistema, primer borrador ni número máximo de llamadas. El tercer intento usa su propio borrador rechazado. No otro juez, capa ni respuesta visible prefabricada.

Focal669pases/0skips,4,03s; incluye230pruebas de estados/feedback más439existentes. Datos y nombres se derivan de cada observación, y un borrador válido no recibe feedback ni otra llamada. Candidata no adoptada: faltan declaraciones/dueñas amplias/Fast y dos respuestas incompletas675. Full651 sigue sólo de baseline anterior. Encuesta26/716/0.
'''
seal(out,out,{'adopted':False,'sources':{p:sha(root/p) for p in ['src/baxy_mind/llm.py','src/baxy_mind/window_prose_facts.py','tests/test_c03_window_state_facts.py','tests/test_c03_window_prose_projection.py']},
    'focal_passed':669,'focal_seconds':4.03,'broad_validation_run':False},note674,[])
out=base/'astra-compositor-focus-feedback675'
private=home/'C03-compositor-focus-feedback675-private'
assert not (out/'RESULT.json').exists()
panel={r['case_id']:r for r in read(private/'panel.json')}
finals=rows(private/'finals.jsonl')
requests=rows(private/'requests.jsonl')
responses=rows(private/'responses.jsonl')
previous={r['case_id']:r for r in rows(home/'C03-compositor-window-states672-private/finals.jsonl')}
measured={r['case_id']:r for r in read(home/'C03-native-focus-feedback673-private/panel.json') if r['arm']=='verified_field_feedback'}
assert len(panel)==len(finals)==17 and len(requests)==len(responses)==22
parity=0
for r in requests:
    if r['call']==2:
        key=r['case_id'] if r['case_id'].endswith('-renamed') else r['case_id']+'-original'
        assert r['payload']==measured[key]['payload'],key
        parity+=1
assert parity==5
assert all(r['response']['choices'][0]['finish_reason']=='stop' for r in responses)
failures={
    'topmost-en-true':'Negation of a conjunction remains ambiguous and focus is not independently answered.',
    'topmost-es-true-renamed':'First draft omits focus and is accepted; no contradiction exists to trigger the current repair.'}
adjudication=[]
for r in finals:
    if not r['case_id'].startswith('topmost-'):
        assert r['calls']==1 and r['final']==previous[r['case_id']]['final']
    assert r['final']
    adjudication.append({**panel[r['case_id']],**r,'verdict':'failed' if r['case_id'] in failures else 'correct',
        'reason':failures.get(r['case_id'],'Individually reviewed: requested state/count, both compound predicates where requested, subject and language preserved.')})
assert sum(r['verdict']=='correct' for r in adjudication)==15
write(private/'adjudication.json',adjudication)
report=['# 675 — 15/17; no empty outputs, two incomplete/ambiguous answers']
for r in adjudication:
    report += ['## '+r['case_id'],r['text'],r['final'],r['verdict']+': '+r['reason'],json.dumps(r['facts'],ensure_ascii=False)]
    report += [json.dumps(x,ensure_ascii=False) for x in responses if x['case_id']==r['case_id']]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note675='''# 675 — reparación integrada15/17; completitud sigue abierta

En los mismos14casos672, la candidata mejora10/14→13/14. Se añaden tres nombres cambiados y cumplen2/3: total15/17. Cinco reintentos coinciden exactamente con las peticiones medidas673 y producen respuestas completas. Los diez controles originales siguen iguales con una sola llamada. Todos17resultados son no vacíos;22llamadas, todasEOS.

Dos fallos quedan abiertos: el inglés activo=true mantiene negación ambigua sin aclarar foco; Brújula7 activo=true omite foco desde el primer borrador, de modo que la guardia de contradicciones no dispara reparación. No se aprueba por haber eliminado salidas vacías. Siguiente: comprobar cobertura de los hechos realmente preguntados dentro del contrato existente, preservando preguntas sólo de maximización o topmost, nombres y negaciones. Distinguir falta de respuesta de contradicción en los datos de reparación; no inventar un valor que el borrador nunca afirmó.

GPU3497,559MiB/RAM719,934MiB/14,234s sin infracciones. Registro intacto; no kernel/UI/voz.674 sigue WIP no adoptado, sin dueñas amplias/Fast. Encuesta26/716/0; C03 activo.
'''
seal(out,private,{'correct':15,'total':17,'same_original_cohort_correct':13,'same_original_cohort_total':14,
    'previous_same_cohort_correct':10,'renamed_correct':2,'renamed_total':3,'empty':0,'native_calls':22,
    'retry_payload_parity673':5,'failed_cases':failures,'source_adopted':False,'resources':read(out/'RESOURCES.json')},note675,
    ['panel.json','requests.jsonl','responses.jsonl','finals.jsonl','adjudication.json','RESULT.md'])
state_path=base/'RELEVO_ACTIVO.json'
state=read(state_path)
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='674 WIP669 focales;675 compositor15/17, dos incompletos. No fuente adoptada. Encuesta26/716/0.',
    continuation='Publicar evidencia671-675. Siguiente: falta de cobertura de foco realmente preguntado, diferenciada de contradicción; preservar preguntas de otros estados. Ver HANDOFF. Ningún proceso activo ni decisión pendiente.',
    previousGoalTurnClassification='progress',previousGoalTurnClassificationReason='Contrato factual y feedback implementados; misma cohorte nativa10/14→13/14, ampliada15/17; evidencia de incompletitud localizada.',activeValidation=None)
write(state_path,state)
handoff='''

## Estado vigente tras675 — sustituye la próxima acción anterior

667–670 publicados4d491328925890d68a922c12349ca75647f15010, remoto verificado. Ahora674WIP no adoptado: llm.py,window_prose_facts.py y tests nuevos de proyección/estados.671valida foco explícito por sujeto;223cohorte105fallos118pases con owner660→223pases, integrada662pases.672compositor10/14, dos vacíos y dos incompletos.673feedback externo del campo6/6 vsgenérico0/6.674integra esos datos en segundo/tercer intento, sin cambiarprimerapetición ni sistema ni máximollamadas; focal669pases4,03s.675original13/14 frente10/14, ampliada15/17; cinco reintentos paridadexacta673,22EOS y cerovacíos. Falta cobertura: inglés activo=true ambiguo y Brújula7 activo=true omitefoco enprimerborrador. No adjudicarcompletitud por ausencia decontradicción ni atribuirvalorafirmado aunaomisión.

Siguiente: contrato de cobertura de lo realmente preguntado, conservando consultas sólo demaximización/topmost, nombres, sujetos e idiomas; feedback de faltante distinto de contradicción. Noequivalentrule/prompt genérico.674noadoptado; declaraciones V8/STT siguen660 deliberadamente, dueñasamplias/Fast pendientes; noFull674. Preservar snapshots671y674antesdecambiarfuente, no restaurarlos por accidente. Sesiones54222/28657/92579 recogidasexit0; ningunaactiva, BAXYmanualcerrado. Scripts baseline671 (aislado),close671-673,compositor672,native673,compositor675,close674-675 YAejecutados. Publicar evidencia sin adoptar la fuente. Encuesta26/716/0, runtime/main intactos, restoC03/UI/voz/Fullfinal abierto.
'''
with (base/'HANDOFF.md').open('a',encoding='utf-8',newline='\n') as stream: stream.write(handoff)
print({'source674':'not adopted','compositor675':'15/17','retry_parity673':5})
