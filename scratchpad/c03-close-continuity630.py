"""Adopt missing-level continuity only after Full and the real product panel."""
from pathlib import Path
import re
import subprocess
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-continuity-product631';private=home/'C03-continuity-product631-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json')=={'exitCode':0,'manifest_unchanged':True}
panel=read(private/'panel.json');events=rows(private/'capture/events.jsonl')
finals=[r for r in events if r.get('type')=='terminal'];assert len(finals)==len(panel)==20
assert sha(private/'panel.json')==sha(home/'C03-clarification-product629-private/panel.json')
failures={'H0012':'Existing noisy identity interpretation failure.',
 'missing-app':'Existing grammatical error: incorrect preposition.',
 'missing-reference-en':'Existing capability refusal instead of missing-reference clarification.',
 'knowledge-discourse':'Existing ciertos bacterias agreement error.'}
judged=[{**c,'terminal':f,'verdict':'failed' if c['case_id'] in failures else 'correct',
 'reason':failures.get(c['case_id'],'Meets the declared response, language and no-effect criterion.')}
 for c,f in zip(panel,finals)]
assert all(f['kind']=='published_final' and not f['timedOut'] for f in finals)
audits=rows(private/'turn-audit.jsonl')
assert not any(r.get('final',{}).get('effect_operations') for r in audits)
volume=[r for r in judged if r['case_id']=='missing-value' or r['case_id'].startswith('missing-level')]
assert len(volume)==9 and all(r['verdict']=='correct' for r in volume)
progress=[r['event'] for r in events if r.get('type')=='event' and r.get('event',{}).get('type')=='boot_stage' and isinstance(r['event'].get('label'),str) and r['event']['label'].strip()]
labels=sorted({r['label'] for r in progress});assert len(labels)==2
write(private/'adjudication.json',judged)
write(private/'progress-adjudication.json',{'events':progress,'labels':labels,
 'new_defects':0,'remaining':'Spanish progress still refers to the user in third person; the whole route is not closed.',
 'ui_verified':False,'voice_verified':False})
report=['# Producto631 — 16/20; nueve aclaraciones de volumen correctas']
for r in judged:report+=['## '+r['case_id'],r['text'],r['terminal']['final'],r['verdict']+': '+r['reason']]
report+=['## Progreso emitido',*labels,'Sin prueba de pantalla ni loopback de voz. No se ejecutó el valor posterior de una aclaración: el contrato de conservación de ese objetivo se verificó en pruebas dueñas.']
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
trace=rows(private/'shell-trace.jsonl');t7=[r for r in trace if r.get('id')=='t7']
start=next(r['ms'] for r in t7 if r['stage']=='submit.received')
end=next(r['ms'] for r in t7 if r['stage']=='response.final' and r['scope']=='bridge')
calls=[r['detail'] for r in t7 if r['stage']=='mind.request.start']
assert sum(str(x).startswith('turn.decide.') for x in calls)==1
note='''# Fuente630 adoptada — la nueva aclaración conserva su propio pedido

628 conserva la orden de volumen que termina con una preposición todavía sin valor.630 evita que el shell la concatene con una aclaración anterior: la mente marca una orden nueva ya reconocida; el shell mantiene su propio objetivo pendiente. startsNewObjective es opcional, false por defecto y no concede efectos. No hay patrones nuevos de lenguaje en C#, prosa fija, cambio de modelo ni nuevo proceso residente.

Producto631 repite exactamente los20casos629:16correctos frente a11. Las9peticiones incompletas de volumen aclaran correctamente en español/inglés/mixed; cero efectos en auditoría y cero nuevos fallos. Persisten H0012, gramática de missing-app, missing-reference-en y gramática de knowledge-discourse. Progreso conserva los dos avisos previos, sin metanarración de idioma; su tercera persona española sigue pendiente. Es transporte de producto, no prueba de pantalla/voz. El siguiente fragmento queda preservado por el contrato probado, pero esta corrida no ejecuta un valor posterior ni acredita la ruta entera.

Full630:exit0, Python10253pass/3omisiones+466subpruebas en589,57s; .NET4457pass/1omisión agregada,0fallos. Omisiones ambientales/opt-in se conservan aparte y no se cuentan como pass. Dueñas previas:Python1254pass/1skip, .NET114pass/0skip;6283375pass/1skip+121subpruebas. Ningún umbral ni suite se relajó. Fuente de ambos extremos comprobada intacta duranteFull. Es validación de este tramo, no cierreC03.

631 midió3499,559MiB GPU y2420,680MiB RAM, sin infracciones.117,234s incluyen la publicación NativeAOT que main.py necesitó al arrancar: no comparar ese total con629como latencia de conversación. El turno reparado emitió su final en627,494ms, una sola decisión en vez de dos. UI y voz juntas y el mínimo global de recursos siguen pendientes.

Encuesta25cubiertos/717abiertos/0NA.632 audita H0040: las negaciones541no estaban respaldadas por las observaciones; queda abierta la reparación del alcance de ventanas, con causa exacta y documentación primaria. Se publica en Goal-c03 sin tocar main. Ninguna decisión pendiente del dueño; autorización536 vigente.
'''
seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'source':630,'finals':20,'correct':16,
 'previous629_correct':11,'volume_clarifications_correct':9,'volume_clarifications_total':9,
 'failed_cases':failures,'new_failures':0,'effects':0,'same_panel_sha256':sha(private/'panel.json'),
 'missing_value_final_ms':round(end-start,3),'missing_value_decision_calls':1,
 'new_progress_defects':0,'progress_labels':labels,'whole_clarification_route_accepted':False,
 'next_slot_execution_tested':False,'ui_or_voice_credit':False,'resources':read(out/'resources.json')},
 note,['panel.json','capture/events.jsonl','turn-audit.jsonl','shell-trace.jsonl','compose-audit.jsonl','adjudication.json','progress-adjudication.json','RESULT.md'])
out=base/'astra-objective-continuity630';assert not (out/'RESULT.json').exists()
log_names=[('c03-continuity630-red.log','DOTNET_RED.log'),('c03-continuity630-python-red.log','PYTHON_RED.log'),('c03-continuity630-python-targeted.log','PYTHON_TARGETED.log'),('c03-continuity630-dotnet.log','DOTNET_OWNERS.log'),('c03-continuity630-python-owners.log','PYTHON_OWNERS.log'),('c03-continuity630-full.log','FULL.log')]
for original,target in log_names:(out/target).write_bytes((Path(os.environ['TEMP'])/original).read_bytes())
full=(out/'FULL.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Full' in full
assert '10253 passed, 3 skipped, 466 subtests passed in 589.57s' in full
matches=re.findall(r'Correctas! - Con error:\s*(\d+), Superado:\s*(\d+), Omitido:\s*(\d+), Total:\s*(\d+), Duración: (.+?) - (\S+\.dll)',full)
assert len(matches)==5 and sum(int(x[0]) for x in matches)==0 and sum(int(x[1]) for x in matches)==4457
prereg=read(out/'PREREG.json');assert all(sha(root/p)==v for p,v in prereg['source_sha256'].items())
paths=[*prereg['source_sha256'],'tests/test_effect_intent.py','tests/test_turn_policy.py','tests/Baxy.Integration.Tests/PlannerAppBoundaryTests.cs','tests/test_price_v8_veto_damage_by_cause.py','experiments/stt_quality/audit_fresh_postweight_stt_sources.py','experiments/stt_quality/evaluate_reserved_stt.py']
(out/'source630.patch').write_bytes(subprocess.check_output(['git','diff','--binary','--',*paths],cwd=root))
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'adopted':True,'full_exit':0,
 'python':{'passed':10253,'skipped':3,'subtests':466,'seconds':589.57},
 'dotnet':[dict(zip(['failed','passed','skipped','total','duration','suite'],[int(x[0]),int(x[1]),int(x[2]),int(x[3]),x[4],x[5]])) for x in matches],
 'dotnet_printed_omissions':len(re.findall(r'^\s*Omitidas ',full,re.MULTILINE)),
 'source_unchanged_during_full':True,'owners':{'python_passed':1254,'python_skipped':1,'dotnet_passed':114,'dotnet_skipped':0},
 'source_files':{p:sha(root/p) for p in paths},'product631':{'correct':16,'total':20,'new_failures':0},
 'goal_complete':False,'survey':{'covered':25,'open':717,'not_applicable':0}})
(out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as stream:stream.write('/artifacts/comprobaciones/C03/astra-objective-continuity630/** -text\n')
state=read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='630 adoptada: Full exit0 Python10253pass/3skips+466subtests,.NET4457pass/1skip;63116/20,9/9volumen y0regresiones.25/717/0.',
 continuation='Publicar630 y evidencia628–632, verificar remoto/main. Después reparar el alcance incorrecto de ventanas auditado632 en effect_intent.py:7821–7823/8424, con lectura por aplicación y regresión ES/EN. No tocar modelo/prosa antes de conservar hechos. UI/voz/recuperación/717requisitos yFullfinal pendientes.',
 publishedSourceCommit='pending_publication_of_validated_source630',pendingOwnerClarification=None,previousGoalTurnClassification='progress')
write(base/'RELEVO_ACTIVO.json',state)
(base/'HANDOFF.md').write_text('# Handoff C03 — fuente630 validada, lista para publicar\n\n'+note+'\nNo procesos de campaña, build o pruebas activos. Siguiente: commit/push630 y comprobar remoto. Luego632: effect_intent.py:7821–7823 trata cualquier ventana como window.active y _strict_catalog_request:8424 devuelve ese dominio. Catálogo ya dispone window.application.status; no repetir una negación inventada desde ventana enfocada. El fallo inglés histórico fue knowledge sin lectura; probar su camino actual. No cambiar modelos sin nueva causa.\n',encoding='utf-8',newline='\n')
p=base/'CHECKPOINT.md';data=p.read_text(encoding='utf-8');old='Fuente publicada626 (`67085974`), main intacto. Candidatos628/630 reparan aclaración y continuidad;629 demuestra por qué628 solo no basta.630 tiene12focalesPython/114.NET y1254dueñasPython/1omisión ambiental; Full630 en curso antes del producto631.'
assert old in data;data=data.replace(old,'Fuente630 validada y lista para publicar; main intacto. Full630 exit0:Python10253pass/3omisiones+466subpruebas,.NET4457pass/1omisión agregada.63116/20 y9/9aclaraciones de volumen, sin nuevas regresiones; persistencia de la respuesta siguiente aún requiere producto.628sola no bastaba y629se conserva como fallo.');p.write_text(data,encoding='utf-8',newline='\n')
print({'adopted_source':630,'product_correct':16,'product_total':20,'full_exit':0,'next_slot_execution_tested':False})
