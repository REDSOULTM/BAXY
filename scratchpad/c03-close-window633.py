"""Seal scoped-query improvement and the downstream defects exposed by634."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-window-product634';private=home/'C03-window-product634-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json')=={'exitCode':0,'manifest_unchanged':True}
panel=read(private/'panel.json');events=rows(private/'capture/events.jsonl')
finals=[r for r in events if r.get('type')=='terminal']
assert len(panel)==len(finals)==12
compose=rows(private/'compose-audit.jsonl')
observations={r['trace']:r['payload'] for r in compose if r.get('payload',{}).get('operation')}
assert len(observations)==10
for index,case in enumerate(panel[:10],1):
    assert observations[f't{index}']['operation']==case['operation']
    if case['name']:
        assert observations[f't{index}']['seen']['requestedName']==case['name']
assert observations['t3']['seen']['hasVisibleWindow'] is False
assert observations['t9']['seen']['windows'][0]['processName']=='Notepad'
assert observations['t9']['seen']['windows'][0]['foreground'] is True
failures={
 'window-name-es':'Provider reports zero Notepad windows, contradicted by the foreground Notepad observation later in the same run. The composer repeats this false observation.',
 'focus-en':'English input is classified mixed and answered in Spanish with ungrammatical El ventana. The selected foreground observation itself is correct.',
}
judged=[{**c,'terminal':f,'observation':observations.get(f't{i}'),
    'verdict':'failed' if c['case_id'] in failures else 'correct',
    'reason':failures.get(c['case_id'],'Matches the requested scope, actual typed observation and language; no write operation.')}
    for i,(c,f) in enumerate(zip(panel,finals),1)]
assert all(f['kind']=='published_final' and not f['timedOut'] for f in finals)
write(private/'adjudication.json',judged)
report=['# Producto634 — 10/12; alcance reparado, inventario e idioma pendientes']
for r in judged:
    report+=['## '+r['case_id'],r['text'],r['terminal']['final'],r['verdict']+': '+r['reason'],json.dumps(r['observation'],ensure_ascii=False)]
progress=[r['event'] for r in events if r.get('type')=='event' and r.get('event',{}).get('type')=='boot_stage' and r['event'].get('label')]
write(private/'progress.json',progress)
report+=['## Progreso',*sorted({r['label'] for r in progress})]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note='''# Fuente633 y producto634 — alcance por aplicación conservado

633 cambia sólo Python: conserva la identidad del catálogo para preguntas de ventanas abiertas/cerradas y elige window.application.status. El argumento cruza su schema. Una mención de ventana, o de visibilidad, ya no basta para seleccionar window.active. No contiene nombres de aplicaciones fijados ni respuestas visibles nuevas; no cambia modelo, perfil ni provider.

Dueñas:3425pass+121subpruebas/0omisiones en64,10s; declaraciones de fuentes17pass/1omisión ambiental en1,95s. Fast exit0, Release23,46s/0warnings/errors. El Full630 sigue como línea base anterior;633 sólo toca Python y no se presenta como Full actual ni cierreC03.

634 ejecuta12turnos del producto registrado, sin hooks.10/12finales correctos. Las8consultas por aplicación eligieron su lectura y nombre correctos; las2consultas de foco eligieron window.active. Steam y Chrome muestran ventanas; Spotify y Paint no. Volumen incompleto y prohibición conservan su conducta. Sólo lecturas, ninguna escritura ni cambio de aplicación. No hay comparación emparejada que permita afirmar cero regresiones globales.

Dos fallos impiden acreditar el requisito completo: Bloc de notas figura sin ventanas en window.application.status y luego aparece como ventana activa; Which window has focus? llega al compositor con idioma mixed y publica El ventana con enfoque… en español. La primera contradicción está en Inventory del provider, antes del modelo. Su reconocimiento usa tokens del nombre visible/ejecutables del AppID; el nombre localizado Bloc de notas y Microsoft.WindowsNotepad_8wekyb3d8bbwe!App no identifican el proceso empaquetado Notepad. Esta es una causa candidata que requiere reproducción y reparación; no basta admitir el texto del modelo.

Recursos634:3497,559MiB GPU,1840,527MiB RAM del árbol medido,28,344s, sin infracciones. Es conductor oculto sin voz física: no acredita UI/voz conjunta ni el mínimo de BAXY. Encuesta25cubiertos/717abiertos/0NA; H0040 sigue abierto porque la generalización expuso el defecto de inventario. Fuente633 se adopta como corrección de alcance, no como cierre de ventanas niC03. Siguiente: identidad de aplicaciones empaquetadas en WindowsInstalledApplicationOpenProvider.cs:1011/1150 y después clasificación de idioma de foco.
'''
seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'source':633,'correct':10,'total':12,
    'application_operations_correct':8,'application_total':8,'foreground_operations_correct':2,
    'failed_cases':failures,'read_operations':10,'write_operations':0,'ui_or_voice_credit':False,
    'resources':read(out/'resources.json'),'whole_window_requirement_accepted':False},
    note,['panel.json','capture/events.jsonl','turn-audit.jsonl','shell-trace.jsonl','compose-audit.jsonl','raw-replies.jsonl','adjudication.json','progress.json','RESULT.md'])
out=base/'astra-window-source633';prereg=read(out/'PREREG.json')
assert all(sha(root/p)==v for p,v in prereg['sources'].items())
for src,dest in [('c03-window633-fast.log','FAST.log'),('c03-window633-pins.log','PIN_OWNERS.log')]:
    (out/dest).write_bytes((Path(os.environ['TEMP'])/src).read_bytes())
assert 'source_quality_gate_passed: mode=Fast' in (out/'FAST.log').read_text(encoding='utf-8-sig')
paths=[*prereg['sources'],'tests/test_effect_intent.py','tests/test_turn_policy.py','tests/test_price_v8_veto_damage_by_cause.py','experiments/stt_quality/audit_fresh_postweight_stt_sources.py','experiments/stt_quality/evaluate_reserved_stt.py']
(out/'source633.patch').write_bytes(subprocess.check_output(['git','diff','--binary','--',*paths],cwd=root))
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'adopted':True,
    'owners':{'passed':3425,'skipped':0,'subtests':121,'seconds':64.10},
    'current_pin_owners':{'passed':17,'skipped':1,'seconds':1.95},'fast_exit':0,'release_seconds':23.46,
    'source_files':{p:sha(root/p) for p in paths},'source_unchanged_during_product':True,
    'product634_correct':10,'product634_total':12,'goal_complete':False,
    'survey':{'covered':25,'open':717,'not_applicable':0}})
(out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as stream: stream.write('/artifacts/comprobaciones/C03/astra-window-source633/** -text\n')
state=read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='633 adoptada:3425pass+121subtests/0skips;17pass/1skip de declaraciones;Fast exit0.63410/12:alcance10/10, inventarioNotepad e idioma foco pendientes.25/717/0.',
    continuation='Publicar633/634 y verificar remoto/main. Después reproducir fallo de identidad empaquetada en WindowsInstalledApplicationOpenProvider.cs:1011/1150; no ampliar coincidencias por título sin autoridad. Then focus-en language. UI/voz/recuperación/717requisitos yFullfinal pendientes.',
    publishedSourceCommit='pending_publication_of_validated_source633',pendingOwnerClarification=None,
    previousGoalTurnClassification='progress',previousGoalTurnClassificationReason='Implemented scoped application reads, validated owners/Fast, and product634 exposed the next provider and language boundaries.')
write(base/'RELEVO_ACTIVO.json',state)
(base/'HANDOFF.md').write_text('# Handoff C03 — fuente633 validada\n\n'+note+'\nSin procesos de campaña/pruebas activos; BAXY manual cerrado y aplicaciones del usuario sin cambios. Publicar antes de reparar provider.\n',encoding='utf-8',newline='\n')
p=base/'CHECKPOINT.md';data=p.read_text(encoding='utf-8');start=data.index('Fuente630 publicada');end=data.index('\n\n## Registro histórico',start)
data=data[:start]+'Fuente633 validada, publicación pendiente. Dueñas3425pass+121subpruebas/0omisiones;17pass/1omisión de declaraciones;Fast exit0. Producto63410/12:selección de lecturas10/10, pero inventario de Bloc de notas e idioma del foco pendientes.25cubiertos/717abiertos/0NA. Full630 es línea base anterior, no Full633. Estado en HANDOFF.md y RELEVO_ACTIVO.json. Los tramos históricos no describen automáticamente la fuente actual.'+data[end:]
p.write_text(data,encoding='utf-8',newline='\n')
print({'source633_adopted':True,'product634_correct':10,'total':12,'survey_unchanged':True})
