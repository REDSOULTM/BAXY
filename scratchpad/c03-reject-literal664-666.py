"""Seal the partial resource stop and restore the validated source bytewise."""
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-conversation-regression666'
private=home/'C03-conversation-regression666-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json')=={'exitCode':1,'manifest_unchanged':True}
assert read(out/'resources.json')['violations']==['system_free_ram_bound']
prereg=read(out/'PREREG.json')
assert all(sha(root/name)==value for name,value in prereg['sources'].items())
panel=read(private/'panel.json')
events=rows(private/'capture/events.jsonl')
finals=[r for r in events if r.get('type')=='terminal']
assert len(panel)==35 and len(finals)==21
visible=[r['event']['entry']['msg'] for r in events if r.get('type')=='event' and r['event'].get('type')=='activity' and r['event']['entry']['src']=='BAXY']
assert visible==[r['final'] for r in finals]
adjudication=[]
for index,case in enumerate(panel):
    final=finals[index] if index<len(finals) else None
    if final is None:
        verdict,reason='not_evaluated','Campaign stopped at the declared system-free-RAM floor before this case; no response credit.'
    else:
        assert final['kind']=='published_final' and not final['timedOut']
        failed=case['case_id']=='H0012'
        verdict,reason=('failed','Known identity-understanding failure: reports interpretation failure instead of identifying BAXY.') if failed else ('correct','Individually reviewed: appropriate identity/greeting, language and subject, without an executed-effect claim.')
    adjudication.append({**case,'terminal':final,'verdict':verdict,'reason':reason})
write(private/'adjudication.json',adjudication)
samples=read(private/'memory-samples.json')
available=[r['available_mib'] for r in samples]
report=['# 666 — parada por RAM libre;21 de35 turnos evaluados']
for row in adjudication:
    report+=['## '+row['case_id'],row['text'],row['terminal']['final'] if row['terminal'] else '(no ejecutado)',row['verdict']+': '+row['reason']]
report+=['## Recursos',json.dumps(read(out/'resources.json')),f'RAM libre mínima de los samples: {min(available)} MiB. No se atribuye toda la presión del PC a BAXY.']
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note='''# 666 — campaña parcial por RAM libre del sistema

El límite declarado detuvo la corrida:21 finales de35,20 correctos y el fallo conocidoH0012;14 casos sin evaluar. No se presenta como una suite35 verde ni se completan respuestas con otra sesión. Las21 actividades coinciden con los21 finales. Fuente y registro permanecieron intactos durante la campaña.

Violación system_free_ram_bound; el último sample registra707,305MiB libres frente al suelo768. Pico del árbol BAXY RAM2388,070MiB,GPU3499,559MiB y68,422s. Esta observación no atribuye toda la presión de memoria del PC al producto; tampoco acredita UI/voz conjunta. El conductor cerró su árbol. Comprobación posterior: ningún proceso BAXY/llama y1250,703MiB disponibles. No se relaja el suelo ni se vuelve a lanzar una carga equivalente sin revisar margen. Candidata664 ya no cualifica por regresión gramatical665; no es necesario repetir esta candidata para decidir su rechazo. Encuesta26/716/0.
'''
seal(out,private,{'source':664,'adopted':False,'planned':35,'evaluated':21,'correct':20,'failed':1,
    'not_evaluated':14,'failed_cases':['H0012'],'exit_code':1,'visible_activity_matches_finals':True,
    'minimum_system_available_mib':min(available),'resources':read(out/'resources.json'),'ui_or_voice_credit':False},note,
    ['panel.json','capture/events.jsonl','compose-audit.jsonl','turn-audit.jsonl','raw-replies.jsonl',
     'memory-samples.json','adjudication.json','RESULT.md'])
out=base/'astra-literal-source664'
assert not (out/'RESULT.json').exists()
pin=read(out/'PREREG.json')
assert sha(root/'src/baxy_mind/llm.py')==pin['llm_sha256']
names=['src/baxy_mind/llm.py','tests/test_price_v8_veto_damage_by_cause.py',
       'experiments/stt_quality/audit_fresh_postweight_stt_sources.py','experiments/stt_quality/evaluate_reserved_stt.py']
(out/'CANDIDATE.patch').write_bytes(subprocess.check_output(['git','diff','--',*names],cwd=root))
temp=Path(os.environ['TEMP'])
for suffix in ['owners','fast']:
    assert (temp/f'c03-literal664-{suffix}.exit.txt').read_text().strip()=='0'
for original,dest in [('owners','OWNERS'),('pins','DECLARATIONS'),('fast','FAST')]:
    (out/f'{dest}.log').write_bytes((temp/f'c03-literal664-{original}.log').read_bytes())
assert '4046 passed, 121 subtests passed' in (out/'OWNERS.log').read_text(encoding='utf-8-sig')
assert '22 passed, 1 skipped' in (out/'DECLARATIONS.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out/'FAST.log').read_text(encoding='utf-8-sig')
# Reverse only the exact candidate bytes; unrelated files and historical pins stay intact.
path=root/'src/baxy_mind/llm.py'
data=path.read_bytes()
old=('"Idioma obligatorio: español. Conserva sin traducir los nombres propios, "\n'
     '                "títulos y rutas. Describe los estados observados con palabras españolas."').encode()
new=('"Idioma obligatorio: español. Fuera de los literales del contrato, "\n'
     '                "no introduzcas palabras inglesas."').encode()
assert data.count(old)==1
path.write_bytes(data.replace(old,new))
assert sha(path)=='61c9da7e0975dabd54f0698f20eef06ade160988b4d8b64b8621516cdd454300'
for name in names[1:]:
    path=root/name; data=path.read_bytes()
    old_digest=pin['llm_sha256'] if name.startswith('tests/') else pin['python_tree_sha256']
    new_digest='61c9da7e0975dabd54f0698f20eef06ade160988b4d8b64b8621516cdd454300' if name.startswith('tests/') else 'f59d75eef59e777ce8288c74630198576bad062b4a398ac229fee3aa341f9c0d'
    assert data.count(old_digest.encode())==1
    path.write_bytes(data.replace(old_digest.encode(),new_digest.encode()))
for name in names:
    assert subprocess.check_output(['git','show','HEAD:'+name],cwd=root).replace(b'\r\n',b'\n')==(root/name).read_bytes().replace(b'\r\n',b'\n')
note='''# 664 — candidata rechazada, fuente660 restaurada

Diez peticiones coinciden exactamente con el brazo663 medido. Dueñas4046 pases+121 subpruebas/0 skips,71,24s; declaraciones22 pases/1 skip ambiental,1,99s; Fast0,Release26,21s,sin advertencias/errores. Esos verdes no bastan: producto665 corrige foreground pero introduce «un ventana», manteniendo23/24. Producto666 se detiene por RAM libre tras21 de35 turnos y conserva el fallo de identidad. No se adopta la instrucción general española.

Patch y logs del candidato preservados. Se restauran únicamente los cuatro ficheros propios a la fuente660 y sus declaraciones; igualdad contra HEAD comprobada, LLM SHA61c9da7e0975dabd54f0698f20eef06ade160988b4d8b64b8621516cdd454300. Modelo/registro/encuesta intactos. Ningún Full664 ni crédito de cierre. Siguiente: alternativa de representación medida663, comprobando gramática y márgenes de RAM antes de otro producto. No seguir acumulando instrucciones equivalentes para estos dos defectos.
'''
seal(out,out,{'adopted':False,'restored_source':660,'candidate_sha256':pin['llm_sha256'],
    'payload_parity':10,'owners':{'passed':4046,'subtests':121,'skipped':0,'seconds':71.24},
    'declarations':{'passed':22,'environmental_skipped':1,'seconds':1.99},'fast_exit':0,'release_seconds':26.21,
    'product665_correct':23,'product665_total':24,'product666_evaluated':21,'product666_planned':35,
    'goal_complete':False},note,[])
state_path=base/'RELEVO_ACTIVO.json'; state=read(state_path)
state.update(checkpoint='664 rechazada:66523/24 por concordancia,666 parcial por RAM libre21/35. Fuente660 restaurada, encuesta26/716/0.',
    continuation='Publicar evidencia662–666. Seguir representación semántica663 con fuente660; revisar RAM libre antes de inferencia. No decisiones pendientes ni procesos activos.',activeValidation=None)
write(state_path,state)
with (base/'HANDOFF.md').open('a',encoding='utf-8',newline='\n') as stream:
    stream.write('\n\n## Cierre662–666 — fuente660 restaurada\n\n'+note+'\nSesiones88588/75548/2009/5205/34747 recogidas exit0;40680 exit1 por suelo de RAM libre. Ninguna activa. Campañas662/663/665/666 y candidata664 selladas. No repetir scripts de preparación/cierre/rechazo.\n')
print({'candidate664':'rejected','restored_source':660,'product666':'20 correct,1 failed,14 not evaluated','minimum_available_mib':min(available)})
