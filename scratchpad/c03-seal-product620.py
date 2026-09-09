"""Preserve the integrated style gain and the remaining social failure."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-gemma-product620';private=home/'C03-gemma-product620-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json')=={'exitCode':0,'manifest_unchanged':True}
panel=read(private/'panel.json')
finals=[r for r in rows(private/'capture/events.jsonl') if r.get('type')=='terminal']
assert len(panel)==len(finals)==35
adjudication=[{**case,'terminal':final,'verdict':'failed' if case['case_id']=='H0032' else 'correct',
               'reason':'Valid social input still becomes interpretation failure; source619 does not change routing.' if case['case_id']=='H0032' else 'Meets declared identity, subject, language and naturalness criterion.'}
              for case,final in zip(panel,finals)]
write(private/'adjudication.json',adjudication)
report=['# Producto620: 34/35; H0032 sigue abierto']
for r in adjudication:
    report+=['## '+r['case_id'],r['text'],r['terminal']['final'],r['verdict']+': '+r['reason']]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note='''# Producto620: mejora de trato confirmada con Gemma

Fuente619, mismo modelo/backend/perfil de614 y mismos35 casos:34correctos frente33. H0218 deja de usar tuteo como apelativo; identidad, vocativos e idiomas se conservan. H0032 sigue publicando un fallo de interpretación por el veto a la pregunta social: no se considera corregido ni se promueve Gemma globalmente.

La ejecución se solapó por error de orquestación con el build Fast619. Baxy16336 y core98892 bloquearon DLL y el build terminó rojo; no es un fallo de fuente ni se oculta. Se repite Fast con el producto ya cerrado antes de621. La conducta capturada se conserva; los87,344s y2758,125MiB RAM no son una comparación limpia de rendimiento con614. GPU1681,988MiB, sin violación; no acredita recursos conjuntos UI/voz.

619 aún requiere Fast recuperado y regresión621 con Qwen registrado antes de adoptarse. Dueñas1049pass/1skip ambiental por archivos de campaña STT ausentes. Encuesta25/717/0 intacta.
'''
seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'source':619,'correct_finals':34,'finals':35,
                 'failed_cases':['H0032'],'resources':read(out/'resources.json'),
                 'concurrent_build':True,'comparative_performance_credit':False,'ui_or_voice_credit':False,
                 'source_adoption_pending':True,'product_promoted':False},
     note,['panel.json','capture/events.jsonl','http-posts.jsonl','turn-audit.jsonl','adjudication.json','RESULT.md'])
out619=base/'astra-style-source619'
for source_name,destination in [('c03-style619-owners.log','OWNERS.log'),('c03-style619-fast.log','FAST_INITIAL_FAILED.log')]:
    (out619/destination).write_bytes((Path(os.environ['TEMP'])/source_name).read_bytes())
state=read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='62034/35, mejora estilo confirmada.619 dueñas1049pass/1skip; Fast inicial rojo por DLL bloqueada durante620, recuperación43153 en curso.',
             continuation='Recoger Fast recuperación43153. Sólo cuando termine, ejecutar621 Qwen registrado. Adjudicar todos35 finales y adoptar/publicar619 sólo sin regresión. Fuente candidata/pins documentados;25/717/0.')
write(base/'RELEVO_ACTIVO.json',state)
(base/'HANDOFF.md').write_text(note+'\nActivo Fast recuperación sesión43153, TEMP/c03-style619-fast-recovery.log. Luego621, sin build simultáneo.612–620 sellados salvo619 fuente pendiente del cierre de validación y publicación.\n',encoding='utf-8',newline='\n')
print('620:34/35; source619 adoption pending')
