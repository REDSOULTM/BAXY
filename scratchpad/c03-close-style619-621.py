"""Reject the shared style candidate after registered-model tone regression."""
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-conversation-regression621';private=home/'C03-conversation-regression621-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json')=={'exitCode':0,'manifest_unchanged':True}
panel=read(private/'panel.json')
finals=[r for r in rows(private/'capture/events.jsonl') if r.get('type')=='terminal']
assert len(panel)==len(finals)==35
failures={'H0012':'Existing identity question still becomes an interpretation failure.',
          'greeting-variant-3':'Existing vocative confusion: assigns Atlas to the user.',
          'H0032':'New tone regression: Vale, ya lo sé is a dismissive acknowledgement, compared with Está bien, gracias in605. Does not meet the warm companion criterion; a terminal is not automatically a correct response.'}
adjudication=[{**case,'terminal':final,'verdict':'failed' if case['case_id'] in failures else 'correct',
               'reason':failures.get(case['case_id'],'Meets the declared criterion.')}
              for case,final in zip(panel,finals)]
write(private/'adjudication.json',adjudication)
report=['# Producto621: 32/35; fuente619 rechazada']
for r in adjudication:
    report+=['## '+r['case_id'],r['text'],r['terminal']['final'],r['verdict']+': '+r['reason']]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note='''# Fuente619 rechazada tras el contraste registrado621

La instrucción más explícita de género y trato mejora Gemma61811/12→12/12 y producto62033/35→34/35. Sin embargo, Qwen registrado621 obtiene32/35: conserva H0012/Atlas y pierde naturalidad cálida en H0032 («Vale, ya lo sé», frente a «Está bien, gracias» en605). Se registra como regresión de tono, no error de operación ni formato. No se flexibiliza ese criterio para publicar la mejora de otro modelo.

Se rechaza la fuente compartida619 y se restauran exactamente llm.py y los tres pins actuales al HEAD validado606. El parche candidato, las pruebas y todos los finales se conservan; no se reabre H0032 en el registro de requisitos porque la fuente candidata nunca fue adoptada. Encuesta25 cubiertos/717 abiertos/0 no aplicables.

Dueñas619:1049pass/1skip ambiental por archivos de campaña STT ausentes. Fast inicial rojo por DLL bloqueadas durante620; recuperación posterior sin BAXY activo:verde, Release5,49s,0advertencias/errores. Esa validación no invalida el rechazo de conducta. No se ejecutó ni se afirma Full619. Full606 sigue ligado a la fuente restaurada:10218pass+466subtests/3skips Python;4452pass/1skip agregado .NET.

621:3499,559MiB GPU/2482,797MiB RAM,91,968s, sin violaciones; no UI/voz conjunta. No cambia modelo, perfil registrado ni adaptador CPU. Se abandona la expansión del guard615–617 y no se encadena otro barrido de prompts. El siguiente contraste debe valorar una alternativa con evidencia y perfil propios sobre los fallos de comprensión/tono, antes de más integración.
'''
seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'source':619,'correct_finals':32,'finals':35,
                 'failed_cases':failures,'source_adopted':False,'resources':read(out/'resources.json'),
                 'ui_or_voice_credit':False,'survey':{'covered':25,'open':717,'not_applicable':0}},
     note,['panel.json','capture/events.jsonl','turn-audit.jsonl','adjudication.json','RESULT.md'])
source_out=base/'astra-style-source619'
paths=['src/baxy_mind/llm.py','tests/test_price_v8_veto_damage_by_cause.py',
       'experiments/stt_quality/audit_fresh_postweight_stt_sources.py','experiments/stt_quality/evaluate_reserved_stt.py']
assert sha(root/paths[0])=='f902b15f904227986457f0631b43b9ca499cba1b0e47d2932d84143a3afd4145'
patch=subprocess.check_output(['git','diff','--binary','--',*paths],cwd=root)
assert patch
(source_out/'candidate619.patch').write_bytes(patch)
(source_out/'FAST_RECOVERED.log').write_bytes((Path(os.environ['TEMP'])/'c03-style619-fast-recovery.log').read_bytes())
assert b'source_quality_gate_passed: mode=Fast' in (source_out/'FAST_RECOVERED.log').read_bytes()
subprocess.run(['git','restore','--source=HEAD','--',*paths],cwd=root,check=True)
for path in paths:
    assert (root/path).read_bytes()==subprocess.check_output(['git','show','HEAD:'+path],cwd=root),path
assert sha(root/paths[0])=='d9ace8ac4adcf83af955276d1ed072b9a9ddff2fe85a26f2fa4511433dcc9425'
write(source_out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'adopted':False,
    'reason':'Registered Qwen621 tone regression H0032; Gemma620 gain does not justify changing the registered product.',
    'owners':{'passed':1049,'skipped':1,'reason':'blind STT campaign inputs absent'},
    'fast_initial_exit':1,'fast_initial_cause':'orchestration overlap with620 locking DLLs',
    'fast_recovery_exit':0,'full_candidate_run':False,'exact_source606_restored':True,
    'restored_files':{path:sha(root/path) for path in paths}})
(source_out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(source_out/'PINS.json',{p.name:sha(p) for p in source_out.iterdir() if p.is_file() and p.name!='PINS.json'})
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as stream:
    stream.write('/artifacts/comprobaciones/C03/astra-style-source619/** -text\n')
with (base/'INVESTIGACION_MODELO_C03.md').open('a',encoding='utf-8',newline='\n') as stream:
    stream.write('\n\n## Cierre617–621\n\n617 confirma20razonamientos nativos pero esquema/semántica insuficientes; no más barrido del subtipo.618 instrucción de trato mejora11/12→12/12. Integración619 mejora Gemma620 a34/35, pero Qwen621 baja a32/35 por tono H0032.619rechazado; fuente606 restaurada byte a byte. Se conserva todo el contraste y la recuperación de Fast por solapamiento con producto; ningún modelo/promoción ni cobertura adicional.\n')
state=read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='612–621 concluidos.619 rechazado por tono Qwen62132/35;606 restaurado exacto. Gemma62034/35 no promovido.25/717/0.',
             continuation='Publicar evidencia612–621 y verificar HEAD=origin; fuente606 intacta. Cambiar de estrategia: herencia+perfil propio de otra alternativa para comprensión/tono antes de integración; no barrer prompts del guard ni repetir los mismos intentos. Pendientes C03 ocho rutas,717requisitos,UI/voz/error-restauración/recursos conjuntos y Full final.',
             pendingOwnerClarification=None,publishedSourceCommit='bbb3a951337661d567da62f62869d81137a4cde3')
write(base/'RELEVO_ACTIVO.json',state)
(base/'HANDOFF.md').write_text(note+'\nNo procesos de campaña ni compilación activos. Evidencia612–621 sellada lista para publicar en Goal-c03. Main intacto. No queda fuente candidata:606 restaurado exacto; no repetir pruebas por restauración de bytes ya validados. El dueño permite históricos/nuevos/encuesta y trabajo autónomo; no queda decisión pendiente.\n',encoding='utf-8',newline='\n')
print('619 rejected; source606 restored exactly;621=32/35')
