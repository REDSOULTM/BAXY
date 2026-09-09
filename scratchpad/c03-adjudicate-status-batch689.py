"""Preserve all73 outcomes and triage shared causes without awarding automatic coverage."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
helper=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(helper[:helper.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-status-batch689'
private=home/'C03-status-batch689-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json')=={'exitCode':0,'manifest_unchanged':True}
panel=read(private/'panel.json')
events=rows(private/'capture/events.jsonl')
finals=[r for r in events if r.get('type')=='terminal']
compose=rows(private/'compose-audit.jsonl')
shell=rows(private/'shell-trace.jsonl')
decisions={r['request_id']:r for r in rows(private/'turn-audit.jsonl') if r['phase']=='final'}
assert len(panel)==len(finals)==73 and sum(r['case_id'].startswith('H') for r in panel)==50
assert all(sha(root/n)==h for n,h in read(out/'PREREG.json')['sources'].items())
# These verdicts follow individual review of the recorded finals and typed facts.
# A published_final is transport success, not proof that the requested task succeeded.
failures={
    'H0023':('window_enumeration','Unnecessary clarification; no window enumeration.'),
    'H0103':('window_enumeration','Unnecessary clarification; no window enumeration.'),
    'H0209':('window_enumeration','Asks to confirm a singular window instead of executing the plural read.'),
    'H0663':('window_enumeration','Repeats the clear request as a question without reading windows.'),
    'windows-all-en':('window_enumeration','Spanish clarification to an English list request; no enumeration.'),
    'windows-focus-mixed':('identity_verification','Fresh correct title but descriptive subject plus con el titulo rejected; final composition fails, same issue687.'),
    'H0384':('requested_measurement','Gives available and total disk space, omitting requested used space.'),
    'disk-used-es':('fresh_read_scope','Computes from conversation values without a fresh read; coincidental numeric agreement is not acceptance.'),
    'H0026':('measurement_semantics','Claims8GB dedicated VRAM despite observed6287261696 dedicated bytes; shared limit must not become dedicated capacity. Also runs duplicate GPU reads.'),
    'H0114':('measurement_semantics','Claims other GPUs are not in use when some adapters are unmeasured/unsupported; unknown is not zero. Requested fullness remains ambiguous.'),
    'gpu-usage-es':('measurement_semantics','Uses GPU engine usagePercent as dedicated-memory usage percentage; ignores observed memory bytes.'),
    'H0342':('requested_measurement','No requested used-RAM amount; describes available RAM and a vague comparison as if it measured usage.'),
    'H0532':('fresh_read_scope','Answers RAM from conversation without a new observation.'),
    'memory-used-es':('requested_measurement','Says used RAM is unknown despite measured total/available; omits requested derived amount.'),
    'H0359':('fresh_read_scope','Incorrectly refuses a notebook battery read as outside capabilities.'),
    'cpu-order-es':('fresh_read_scope','Clear topicalized CPU usage request ends in interpretation failure, no measurement.'),
    'H0450':('fresh_read_scope','Clear clock request ends in interpretation failure.'),
    'H0499':('fresh_read_scope','Incorrectly refuses current date as outside capabilities.'),
    'H0602':('fresh_read_scope','Clear clock request ends in interpretation failure.'),
    'clock-date-en':('fresh_read_scope','Incorrectly refuses current local date; conversation answer, no read.'),
    'H0127':('read_confirmation','wifi.status enters a confirmation instead of answering the local read. Catalog labels it PrivacySensitive; identify policy cause before changing it.'),
    'H0433':('pending_confirmation','Prior Wi-Fi confirmation remains pending; composition also fails. No new requested read.'),
    'network-wifi-en':('read_confirmation','New wifi.status confirmation; requested network not identified.'),
    'network-internet-es':('pending_confirmation','Unrelated Internet check is consumed by pending Wi-Fi confirmation.'),
}
for case_id in ['H0364','H0650','H0675','processes-top3-en','processes-top2-es','H0383','audio-status-en','audio-order-es']:
    failures[case_id]=('pending_confirmation','Pending Wi-Fi confirmation consumes this independent read. No process/audio operation; this run does not isolate that provider or its normal prose.')
numeric_review={'H0111','H0162','H0539','H0655','H0508','memory-total-en'}
adjudication=[]
for i,(case,final) in enumerate(zip(panel,finals),1):
    trace=[r for r in shell if r['scope']=='turn' and r['id']==f't{i}']
    request_ids=[m[1] for r in trace if (m:=re.search(r'turn\.decide\.id\.(\d+)\.',r['detail'] or ''))]
    related_decisions=[decisions[k] for k in request_ids if k in decisions]
    drafts=[r for r in compose if r.get('trace')==f't{i}']
    core_calls=[r['detail'] for r in trace if r['stage']=='core.call.start']
    if case['case_id'] in failures:
        cause,reason=failures[case['case_id']];verdict='failed'
    elif case['case_id'] in numeric_review:
        cause='memory_units_review';verdict='needs_verification'
        reason='Reports nominal16GB from observed total16539508736bytes. Need explicit usable-versus-installed measurement and units, not an assumed conversion. Preserve literal output; no correctness or coverage credit yet.'
    else:
        cause=None;verdict='correct_observed_run'
        reason='Individual final agrees with fresh observed requested fields and language. Coverage still requires relevant generalization across states/values; this verdict alone does not close a survey requirement.'
        assert final['kind']=='published_final' and drafts and core_calls,case['case_id']
    assert not final['timedOut']
    adjudication.append({**case,'turn_id':f't{i}','terminal':final,'decisions':related_decisions,
        'core_calls':core_calls,'compose':drafts,'verdict':verdict,'cause_group':cause,'reason':reason})
counts=dict(Counter(r['verdict'] for r in adjudication))
assert counts=={'failed':32,'correct_observed_run':35,'needs_verification':6},counts
write(private/'adjudication.json',adjudication)
report=['# Tanda689:50requisitos y23variantes, adjudicación completa',
    '35respuestas correctas en esta corrida,32fallos y6pendientes de verificar unidades/capacidad. No se actualiza cobertura de encuesta. Las decisiones se enlazan por request_id obtenido de shell-trace, nunca por posición: hay56decisiones para73turnos por confirmaciones y rutas de shell.',
    'La memoria libre expresada en bytes es fiel al dato, pero poco cómoda de leer; se conserva como observación de presentación. La identidad GPU en primera persona se entiende aquí como el PC anfitrión, no como prueba de hardware propio del asistente.']
for r in adjudication:
    report += ['## '+r['case_id']+' — '+r['group'],r['text'],r['terminal']['final'],r['verdict']+': '+r['reason'],
        'Criterio: '+r['criterion'],json.dumps({'core_calls':r['core_calls'],'decisions':r['decisions'],'compose':r['compose']},ensure_ascii=False)]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
resources=read(out/'resources.json')
assert not resources['violations']
plan=base/'STATUS_BATCH689_PLAN.json'
note='''# 689 — tanda50 ejecutada y adjudicada completa

73turnos:50requisitos de encuesta y23variantes de diez grupos, con textos/notas/criterios fijados antes de ejecutar.35respuestas correctas en esta corrida,32fallos y6pendientes de verificar distinción entre memoria instalada/utilizable y unidades. Son resultados observados, no35coberturas nuevas: encuesta26cubiertos/716abiertos/0NA intacta. Todos los finales y hechos se conservan en el informe privado.

Causas compartidas: enumeración de ventanas no ejecutada; lecturas claras que se rechazan o responden desde historial; valores de memoria/GPU confundidos y cantidades derivables omitidas; falso rechazo descriptivo de foco687; confirmación de wifi.status que arrastra consultas posteriores independientes. No atribuir los fallos de procesos/audio a sus proveedores: no llegaron a ejecutarse. La correlación de decisiones usa request_id de shell-trace, no posición (56decisiones para73turnos). Una sonda inicial por posición produjo IndexError y se descartó antes de adjudicar.

GPU3499,559MiB/RAM2519,566MiB/140,484s, sin infracciones ni timeout; registro y fuente686publicada intactos. No UI/voz conjunta ni mínimo global. Siguiente reparación por causas compartidas de esta misma tanda, conservando sus50requisitos y23variantes: primero recuperar el contrato de lectura y las cantidades observadas, y separar la política/confirmación pendiente de la capacidad del proveedor. Herencia542 ya documentó confusión de8GBGPU: arregló alcance, no presentación; no repetir su investigación. No fuente nueva adoptada por esta evaluación.
'''
seal(out,private,{'requirements':50,'variants':23,'total':73,'counts':counts,
    'by_group':{g:dict(Counter(r['verdict'] for r in adjudication if r['group']==g)) for g in sorted({r['group'] for r in adjudication})},
    'cause_groups':dict(Counter(r['cause_group'] for r in adjudication if r['cause_group'])),
    'resources':resources,'plan_sha256':sha(plan),'survey':{'covered':26,'open':716,'not_applicable':0},
    'new_coverage':0,'ui_or_voice_credit':False,'goal_complete':False},note,
    ['panel.json','turns.jsonl','capture/events.jsonl','compose-audit.jsonl','turn-audit.jsonl','shell-trace.jsonl','raw-replies.jsonl','adjudication.json','RESULT.md'])
state_path=base/'RELEVO_ACTIVO.json'
s=read(state_path)
s.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),activeValidation=None,
    checkpoint='686publicada;689terminada73/73:35correctas,32fallos,6verificación numérica pendiente. Encuesta26/716/0.',
    continuation='Trabajar por causas compartidas de tanda689: lectura fresca/interpretación, proyección numérica y confirmación de lectura que bloquea consultas independientes. No repetir matriz antes de cambiar una causa; conservar73casos y variantes. Ver astra-status-batch689/RESULT.json y privado adjudication.json.',
    previousGoalTurnClassification='progress',previousGoalTurnClassificationReason='686validada/publicada; primera tanda50 completa con73turnos y adjudicación individual. La matriz de fallos cambia el siguiente trabajo a causas compartidas, no microcampañas por literal.')
write(state_path,s)
print(counts)
