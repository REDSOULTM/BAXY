"""Adopt the scoped progress metadata repair with product evidence and remaining failures."""
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-conversation-regression627';private=home/'C03-conversation-regression627-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json')=={'exitCode':0,'manifest_unchanged':True}
panel=read(private/'panel.json');events=rows(private/'capture/events.jsonl')
finals=[r for r in events if r.get('type')=='terminal'];assert len(panel)==len(finals)==35
failures={'H0012':'Existing colloquial identity question still becomes an interpretation failure.',
          'greeting-variant-3':'Existing addressee error: calls the user Atlas.'}
judged=[{**case,'terminal':final,'verdict':'failed' if case['case_id'] in failures else 'correct',
         'reason':failures.get(case['case_id'],'Meets declared subject, language and naturalness criterion.')}
        for case,final in zip(panel,finals)]
progress=[r['event'] for r in events if r.get('type')=='event' and r.get('event',{}).get('type')=='boot_stage' and r['event'].get('stage')=='understanding' and r['event'].get('phase')=='active']
assert progress
published_progress=[r for r in progress if isinstance(r.get('label'),str) and r['label'].strip()]
labels=sorted({r['label'] for r in published_progress})
assert len(labels)==2
assert not any('mezcla español e inglés' in text or 'analizando el contenido' in text for text in labels)
write(private/'adjudication.json',judged)
write(private/'progress-adjudication.json',{'events':progress,'unique_labels':labels,
    'language_metanarration_removed':True,'remaining_defect':'Spanish still refers to the user in third person; progress route naturalness is not closed.',
    'ui_visibility_verified':False,'voice_verified':False})
report=['# Producto627: 33/35 finales; metadatos retirados del aviso de progreso']
for r in judged:
    report+=['## '+r['case_id'],r['text'],r['terminal']['final'],r['verdict']+': '+r['reason']]
report+=['## Avisos emitidos al transporte de interfaz',*labels,
         'El evento boot_stage prueba transporte, no observación de pantalla ni voz. La tercera persona española sigue pendiente.']
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note='''# Fuente626 adoptada: el progreso no narra la política de idioma

El narrador de progreso mixed recibe sólo el contrato español permitido por identidad. Las peticiones explícitas de inglés conservan su idioma; el resto de la conversación conserva la política completa de spanglish. No se cambian modelo, sampler, fases, números, guardas de hechos ni presupuesto/reintentos. La instrucción simplificada se conserva también al reparar un borrador.

625 verificó las cuatro fases y ocho controles ES/EN.627, con Qwen registrado y sin hooks, mantiene33/35 finales como605; siguen H0012 y Atlas, sin nuevas regresiones. El transporte boot_stage ya no contiene la explicación interna de mezcla de idiomas. Esto no acredita pantalla ni voz y la referencia española a «la solicitud del usuario» sigue pendiente: la ruta completa de progreso no está cerrada.

Validación626:200pruebas focales; dueñas ampliadas1363pass/1skip ambiental por archivos de campaña STT ausentes; Fast verde, Release20,29s,0advertencias/errores. Se conservan los contratos de hechos y los pines históricos consumidos; sólo se actualizan los pines de la fuente vigente. No se ejecutó Full626: la fuente sólo toca Python y se exige Full del candidato final. Full606 queda como línea base histórica, no como prueba del código626.

Producto627:3499,559MiB GPU/2361,191MiB RAM,88,750s, sin infracciones; UI y voz no estaban activas juntas. Encuesta25 cubiertos/717 abiertos/0 no aplicables. No se ha promovido un modelo ni se ha cerrado C03. Fuente626 y evidencia622–627 se publican en Goal-c03; main permanece intacto.
'''
seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'source':626,'finals':35,'correct_finals':33,
                 'failed_cases':failures,'new_final_regressions':0,'progress_events':len(progress),
                 'published_progress_events':len(published_progress),
                 'unique_progress_labels':labels,'language_metanarration_removed':True,
                 'whole_progress_route_accepted':False,'ui_or_voice_credit':False,
                 'resources':read(out/'resources.json'),'survey':{'covered':25,'open':717,'not_applicable':0}},
     note,['panel.json','capture/events.jsonl','turn-audit.jsonl','adjudication.json','progress-adjudication.json','RESULT.md'])
out=base/'astra-progress-source626'
assert sha(root/'src/baxy_mind/llm.py')=='464603566c9dc66204cc75e45a79c8058063d0bb06fe6ff554bf56529e5ea73e'
for original,destination in [('c03-progress626-targeted.log','TARGETED.log'),('c03-progress626-owners.log','OWNERS.log'),('c03-progress626-fast.log','FAST.log')]:
    (out/destination).write_bytes((Path(os.environ['TEMP'])/original).read_bytes())
assert b'1363 passed, 1 skipped' in (out/'OWNERS.log').read_bytes()
assert b'source_quality_gate_passed: mode=Fast' in (out/'FAST.log').read_bytes()
paths=['src/baxy_mind/llm.py','tests/test_c03_request_preservation.py','tests/test_price_v8_veto_damage_by_cause.py',
       'experiments/stt_quality/audit_fresh_postweight_stt_sources.py','experiments/stt_quality/evaluate_reserved_stt.py']
(out/'source626.patch').write_bytes(subprocess.check_output(['git','diff','--binary','--',*paths],cwd=root))
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'adopted':True,'scoped_change':'Progress-only mixed output language; remove irrelevant conversation/language-analysis metadata.',
    'targeted_passed':200,'owners_passed':1363,'owners_skipped':1,'owners_skip_reason':'blind STT campaign inputs absent',
    'fast_exit':0,'release_seconds':20.29,'release_warnings':0,'release_errors':0,'full_run':False,
    'registered_product627_final_correct':33,'registered_product627_final_total':35,'new_final_regressions':0,
    'whole_progress_route_accepted':False,'source_files':{path:sha(root/path) for path in paths}})
(out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as stream:stream.write('/artifacts/comprobaciones/C03/astra-progress-source626/** -text\n')
state=read(base/'RELEVO_ACTIVO.json')
if 'blockedAudit' in state: state['resolvedBlockedAudit']=state.pop('blockedAudit')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='626 adoptada: progreso mixed sin metanarración.1363pass/1skip+Fast verde;62733/35sin regresión, dos etiquetas de progreso sin análisis del idioma.25/717/0.',
             continuation='Publicar fuente626/evidencia622–627 y verificar remoto. Continuar C03: identidad H0012/vocativo Atlas, naturalidad de progreso y otras rutas;717requisitos abiertos, UI/voz/recuperación/recursos conjuntos/Full final. No repetir los cambios de estilo619 ni el subtipo615–617 ni promover Ministral622–624.',
             previousGoalTurnClassification='progress',pendingOwnerClarification=None,publishedSourceCommit='pending_publication_of_validated_source626')
write(base/'RELEVO_ACTIVO.json',state)
(base/'HANDOFF.md').write_text(note+'\nNo procesos de prueba ni compilación activos. Fuente626 validada lista para commit/push. Los estudios622–624 no promovieron Ministral:14/20guardia original,11/20subtipo, serialización user-user reparada sólo en diagnóstico6234/12prosa;624nativo8/12 e identidad0/12 con1corte. La autorización536 permite históricos/nuevos/encuesta y sigue vigente; no hay decisión pendiente.\n',encoding='utf-8',newline='\n')
with (base/'INVESTIGACION_MODELO_C03.md').open('a',encoding='utf-8',newline='\n') as stream:
    stream.write('\n\n## Progreso625–627\n\n565 había rechazado reformular el destinatario.625 conserva destinatario/fase/modelo/sampler y elimina sólo metadatos de política mixed que605 narraba. Cuatro fases mixtas y ocho controles ES/EN conservan estado/pasos; la metanarración desaparece, la tercera persona no.626 integra la selección de español para progreso mixed, con inglés explícito intacto y política completa en conversación.1363pass/1skip+Fast;62733/35finales y transporte de progreso sin explicación del idioma. Fuente parcial adoptada, no cierre de ruta/UI/voz ni nueva promoción de modelo.\n')
print({'adopted_source':626,'finals_correct':33,'progress_events':len(progress),'unique_labels':len(labels)})
