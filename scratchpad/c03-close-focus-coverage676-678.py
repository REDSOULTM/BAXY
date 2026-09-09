"""Adopt the validated focused repair and preserve its product regression evidence."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-close-window-facts660-661.py').read_text(encoding='utf-8')
source=source[:source.index("out = base / 'astra-window-facts-source660'")]
source=source.replace('window-facts-product661','focus-coverage-product678')
source=source.replace("old = home / 'C03-language-product655-private'", "old = home / 'C03-projection-product669-private'")
source=source.replace("['windows'][0]['foreground']", "['windows'][0]['is_current_window_for_user_interaction']")
source=source.replace("failed = case['case_id'] == 'focus-variant-es'", 'failed = False')
source=source.replace('# Producto661 — 23/24, sin cambios en los24 finales de655', '# Producto678 — 24/24; respuestas iguales a669')
start=source.index("note = '''")
end=source.index('seal(out, private',start)
source=source[:start]+'''note = """# 678 — regresión de producto24/24

Las24consultas y sus respuestas finales coinciden con669. Veintidós observaciones revisadas con snapshots independientes antes/después:16 lecturas por aplicación y cuatro referencias correctas, foco ChatGPT y cantidades actuales estables. Todas24actividades igualan los finales. Steam/WhatsApp siguen cerrados y Chrome tiene una ventana; no se acredita su estado positivo de661/665.

GPU3497,559MiB/RAM2297,262MiB/40,938s, sin infracciones y con fuentes/registro intactos. No UI/voz conjunta ni comparación emparejada de ahorro. La primera comprobación de margen tuvo2604,5MiB disponibles y no lanzó el producto; tras cierre normal de servidores MSBuild/compilador hubo3665,8MiB y se ejecutó una única campaña678. BAXY volvió a quedar cerrado. Encuesta26/716/0; C03 no completo.
"""
''' + source[end:]
source=source.replace("'source':660, 'correct':23", "'source':676, 'correct':24")
source=source.replace("'all_finals_identical_to655':True", "'all_finals_identical_to669':True")
source=source.replace("'failed_cases':['focus-variant-es']", "'failed_cases':[]")
exec(compile(source,__file__,'exec'))

out=base/'astra-focus-coverage-source676'
assert not (out/'RESULT.json').exists()
prereg=read(out/'PREREG.json')
assert all(sha(root/name)==value for name,value in prereg['sources'].items())
temp=Path(os.environ['TEMP'])
for suffix,name in [('owners','OWNERS'),('declarations','DECLARATIONS'),('fast','FAST'),('fast-preflight-error','FAST_ENVIRONMENT_ERROR')]:
    (out/(name+'.log')).write_bytes((temp/f'c03-focus-coverage676-{suffix}.log').read_bytes())
for suffix in ['owners','declarations','fast']:
    assert (temp/f'c03-focus-coverage676-{suffix}.exit.txt').read_text().strip()=='0'
assert '2566 passed, 121 subtests passed' in (out/'OWNERS.log').read_text(encoding='utf-8-sig')
assert '600 passed, 1 skipped' in (out/'DECLARATIONS.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out/'FAST.log').read_text(encoding='utf-8-sig')
assert read(base/'astra-compositor-focus-coverage677/RESULT.json')['correct']==17
assert read(base/'astra-focus-coverage-product678/RESULT.json')['correct']==24
note='''# 676 — conservación y reparación del foco adoptadas

La proyección mantiene el significado de foreground sin confundirlo con siempre encima. El contrato factual contrasta afirmaciones explícitas con el foco tipado de cada ventana. Si se pregunta directamente por foco en una observación de una sola ventana, detecta también su omisión; identificar la ventana activa para preguntar por maximización no añade una petición de foco. El feedback distingue contradicción de falta de respuesta y deriva sujeto/valores del snapshot. Va en los datos del reintento existente; no cambia primer borrador, sistema, modelo ni máximo de llamadas. No respuestas visibles fijas ni segunda capa de narración.

Nueva cohorte de cobertura64: baseline de conducta50fallos/14pases→64pases; el error previo de API64fallos se conserva aparte. Focal integrada733pases/0skips,4,52s. Dueñas declaradas23ficheros:2566pases+121subpruebas/0skips,25,18s. Declaraciones600pases/1skip ambiental,5,05s: faltan entradas de campaña ciega STT. Fast exit0,Release31,47s,0advertencias/errores. Se conserva el preflight fallido por usar inicialmente Python de producto sin ruff; el gate verde usa BAXYQuality configurado.

Compositor677 mismos17casos15/17→17/17:24llamadas EOS, diez controles en una llamada y siete compuestos en dos. Producto67824/24 sin alterar respuestas669, con observaciones independientes. La gramática es delimitada; no prueba comprensión universal, cobertura de todas las preguntas ni todas las negaciones. Se adopta esta reparación acotada. Encuesta26/716/0, ocho rutas/reserva/UI/voz/recuperación/Full final siguen abiertos. Full651 es baseline anterior, no validación final676; el encargo sólo exige otro Full al adoptar C#+Python juntos o cerrar C03, y esta tanda es Python.
'''
seal(out,out,{'adopted':True,'sources':prereg['sources'],'python_tree_sha256':prereg['python_tree_sha256'],
    'behavioral_baseline':{'failed':50,'passed':14},'new_focus_coverage_passed':64,'focal_passed':733,
    'owners':{'files':23,'passed':2566,'subtests':121,'skipped':0,'seconds':25.18},
    'declarations':{'passed':600,'environmental_skipped':1,'seconds':5.05},
    'fast_exit':0,'release_seconds':31.47,'full_baseline':651,'full676_run':False,
    'compositor677_correct':17,'compositor677_total':17,'product678_correct':24,'product678_total':24,
    'goal_complete':False},note,[])
state_path=base/'RELEVO_ACTIVO.json'
state=read(state_path)
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='676 adoptada:733 focales;2566dueñas+121subtests;declaraciones600/1skip ambiental;Fast0;67717/17;67824/24.',
    continuation='Auditar/commitear/push676-678 ahora; main intacto. Luego acreditar H0104 con literal y variantes del producto, sin adjudicar por familia; encuesta26/716/0 intacta. BAXY cerrado, ninguna decisión pendiente.',
    activeValidation=None,previousGoalTurnClassification='progress',
    previousGoalTurnClassificationReason='Reparación de foco y cobertura676 validada y adoptada; mismas17consultas compositor completas y producto24/24 sin regresión observada.')
write(state_path,state)

matrix=root/'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
lines=matrix.read_text(encoding='utf-8-sig').splitlines()
evidence=' Actualización676: conservación/feedback de foco adoptados;733focales,2566dueñas+121subpruebas/0skips,declaraciones600pases/1skip ambiental,Fast0. [Compositor677](../../../artifacts/comprobaciones/C03/astra-compositor-focus-coverage677/RESULT.md) mismos17casos completos; [producto678](../../../artifacts/comprobaciones/C03/astra-focus-coverage-product678/RESULT.md)24/24. Gramática acotada; encuesta26/716/0 y C03 global abiertos, sin crédito de UI/voz conjunta ni Full final.'
for index,line in enumerate(lines):
    if line.startswith('| G04.02 /') or line.startswith('| G06.01 /'):
        assert line.endswith('|')
        lines[index]=line[:-1]+evidence+' |'
    if line.startswith('| G03C.06 /'):
        assert line.endswith('|')
        lines[index]=line[:-1]+' Evidencia disponible — owner C07: producto678 GPU3497,559MiB/RAM2297,262MiB; sin UI/voz conjunta, estado de la fila sin cambio. |'
matrix.write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
handoff='''# C03 — fuente676 adoptada; publicación pendiente de verificar

Goal activo, rama Goal-c03, main intacto5f572ee1b48cb5e2543ee5e06510e51057c9c845. Autoridad completa en C:/Users/usuario/.codex/attachments/b424eff2-0702-4cc9-871a-451d31ecf314/goal-objective.md. Sin subagentes ni decisión pendiente. Conservar otra tarea del dueño en VS Code y sus cambios. Último HEAD publicado antes de676: a97e1142fad493af888d0c56a240a79947379f7c.

676 conserva foco tipado, distingue contradicción de omisión realmente preguntada y envía evidencia al reintento existente.733focales; dueñas23archivos2566pases+121subpruebas/0skips25,18s; declaraciones600pases/1skip ambiental5,05s; Fast0,Release31,47s. Primer Fast preflight usó por error RuntimePython sin ruff; el verde usa BAXYQuality por defecto. Fuentes/tests/pins de programa actuales en astra-focus-coverage-source676/RESULT.json. No Full676: Full651 es baseline anterior10411pases/3skips+466subtests; .NET4469pases/1skip agregado y16opt-in aparte. Otro Full al adoptar C#+Python juntos o cierre final, no cada edición Python.

677 mismos17casos15/17→17/17; las17primeras peticiones y borradores iguales675. Diez controles en una llamada, siete compuestos en dos,24EOS.678 producto24/24, respuestas idénticas669,22observaciones y snapshots independientes;16lecturas por app/cuatro referencias correctas. Steam/WhatsApp cerrados, Chrome1ventana, focoChatGPT. GPU3497,559MiB/RAM2297,262MiB/40,938s; no UI/voz conjunta, mínimo global ni ahorro demostrado. Campo alwaysOnTop de los fixtures no es una capacidad nueva del proveedor. Gramática delimitada; no verdad semántica universal.

Siguiente acción: auditar y publicar676–678 antes de otra fuente. Después H0104 («qué ventana está activa»), el único requisito de encuesta localizado sobre foco, sigue OPEN: acreditar original/variantes por producto y sumar sólo si se demuestra. Encuesta742/rev1248:26cubiertos/716abiertos/0NA; SHA237c14900a9e36e2e5f6071f132ad916a234ecb39a77e0dd497ef2565eceb2b7 intacto. Generalizar nombres/estados/orden/idioma; no cobertura por familia. El histórico/nuevos están autorizados por536. Restan ocho rutas, cien respuestas, encuesta, UI real, loopback íntegro/AEC separado, avería→restauración→normal y Full final. Voz humana/wake/FAR/FRR deC08; continuidadC04–C09 documentada, no ejecutar sus goals.

BAXY manual cerrado y ninguna campaña activa. Sesiones6542/6413/4699/67379 recogidasexit0. Producto678 se lanzó una vez: primer chequeo de RAM2604,5MiB lo impidió; cierre normal de build-server dejó3665,8MiB. Runtime Qwen4B2507Q4_K_M/b9980 sin cambios, manifestSHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed. Python C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8; calidad por defecto scripts/test_source_quality.ps1, NO -QualityPython apuntandoalruntime. No solapar inferencia/build/Full. Steam/Discord/WhatsApp cerrados por autorización; preservar VSCode/ChatGPT. No eludir bloqueo anterior de Computer Use sobre Opera.

Prepare676, owner676, compositor677, close677, product678 y close676-678 YAejecutados. Snapshots671/674 y evidencias anteriores sellados; no repetir cierres ni editar sus pins. La auditoría nueva de publicación será de sólo lectura. Mantener el goal activo hasta demostrar todo el cierre.
'''
(base/'HANDOFF.md').write_text(handoff,encoding='utf-8',newline='\n')
print({'adopted':676,'product678':'24/24','compositor677':'17/17','goal_complete':False})
