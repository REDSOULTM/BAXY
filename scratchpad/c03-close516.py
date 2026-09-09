"""Seal source/test evidence for the qualified memory configuration repair."""
from pathlib import Path
from datetime import datetime, timezone
import difflib, hashlib, json, os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-memory-configuration516'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-memory-configuration516-private'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, value): p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert 'Superado:  1962' in (out/'owners-final.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out/'fast-final.log').read_text(encoding='utf-8-sig')
sources = ['src/Baxy.App/NaturalMemoryRequestParser.cs','tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs','tests/Baxy.Integration.Tests/MemoryHandlersTests.cs']
patch=''
for source in sources:
    before=(private/Path(source).name).read_text(encoding='utf-8-sig').splitlines(keepends=True)
    after=(root/source).read_text(encoding='utf-8-sig').splitlines(keepends=True)
    patch+=''.join(difflib.unified_diff(before,after,fromfile='a/'+source,tofile='b/'+source))
(out/'SOURCE.patch').write_text(patch,encoding='utf-8')
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'baseline':{'passed':22,'failed':10,'skips':0,'milliseconds':643,'session':71205,'exit':1},'focal':{'passed':36,'failed':0,'skips':0,'milliseconds':588,'session':91189,'exit':0},'first_owners':{'passed':1961,'failed':1,'skips':0,'duration':'4 m 1 s','session':77040,'exit':1},'export_focal':{'passed':1,'failed':0,'skips':0,'milliseconds':134,'session':88772,'exit':0},'final_owners':{'passed':1962,'failed':0,'skips':0,'duration':'3 m 47 s','session':31964,'exit':0},'fast':{'passed':True,'release_seconds':3.47,'warnings':0,'errors':0,'session':66617,'exit':0,'initial_preflight':'Wrong runtime Python selected, no ruff. Existing dedicated BAXYQuality environment used on retry, no dependency or threshold change. Failure retained.'},'change':'Anchored private-memory configuration grammar replaces exact configuration aliases; keeps original Classify guards and encrypted memory.configure route, confirms only via existing kernel flow. No new model invocation, fixed visible response or public capability. Existing export test now checks typed destination/integrity/sync data instead of a stale localized JSON substring, preserving file/replay/privacy assertions.','source_sha256':{s:sha(root/s) for s in sources},'limits':'No Full during repair, no actual desktop or physical voice. Product517 prepared to validate real disable and prior eight controls. Status/progress prose and whole C03 remain open.'})
(out/'RESULT.md').write_text('''# Configuración de la memoria privada: fuente validada

La petición «Desactiva la memoria privada.» ya reconoce la operación privada existente. Una gramática anclada combina verbos de habilitar/deshabilitar y on/off con la memoria propia y calificadores locales, privados o personales ES/EN. Sustituye los alias de configuración; conserva los filtros anteriores, el cifrado y la confirmación del kernel. No añade generación ni respuestas visibles fijas.

El diagnóstico previo dejó10 fallos y22 pases. Después pasan36 controles focales, con variantes válidas y menciones que no autorizan cambios. La primera batería dejó1961 pases y un fallo: un test antiguo buscaba Documentos/BAXY dentro del JSON que ya declara Documents/BAXY. Se comprobó el contrato con el exportador y su otro test dueño. La aserción corregida verifica campos estructurados de destino, integridad, sincronización y replay, conservando los controles de ruta real, hash y privacidad. Ese test pasa1/1; la repetición de memoria pasa1962/1962, cero omisiones, en3m47s.

Fast pasa completo; Release3,47s, cero advertencias y errores. El primer preflight eligió por error el Python del producto, sin ruff; se conserva el fallo y se utilizó el entorno de calidad ya instalado. No se instalaron dependencias ni relajaron versiones. Sesiones71205/91189/77040/88772/31964/66617 recogidas; servidores de compilación apagados.

La diferencia de esta tanda frente al WIP anterior está en SOURCE.patch y las tres copias anteriores se guardan privadas. No es el cierreC03.517 verificará la deshabilitación real en un perfil aislado, con el resto de controles de memoria. La narración de resultados y progreso, la aceptación fresca, UI/voz, recursos conjuntos y Full final siguen pendientes.
''',encoding='utf-8')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
note='\n516 validado: focal36/36; primer owner1961pass1fail por expectativa obsoleta de destino localizado, contrastada y sustituida por hechos JSON más precisos, sin alterar exportador. Export1/1; owners-final1962pass/0skips3m47s, sesión31964exit0. Fast66617exit0, Release3,47s0warnings/errors; preflight inicial con intérprete equivocado preservado, entorno BAXYQuality correcto al repetir. Buildservers apagados. Fuente nueva sólo parser privado y tests dueños; llm512 intacto.517 listo para ejecución real9casos;518 auditoría de entrenamiento cerrada antes:92coincidencias/112sincoincidencia(101originales completos), ninguna reserva certificada. Siguiente número libre519.\n'
for name in ['CHECKPOINT.md','HANDOFF.md']:
    with (base/name).open('a',encoding='utf-8') as stream:stream.write(note)
relay_path=base/'RELEVO_ACTIVO.json';relay=json.loads(relay_path.read_text(encoding='utf-8-sig'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='Fuente516 validada:1962 memoria/0skips + Fast; fuente llm512.518 entrenamiento cerrado. Sin procesos de diagnóstico activos.',continuation='Ejecutar517, recoger y verificar enabled=false real. Después progreso/resultados y reserva: exposición >483/contexto/fuentes de mezcla. C03 íntegro activo.')
write(relay_path,relay)
report=base/'ESTADO_PARA_DUENO_2026-09-08.md'
text=report.read_text(encoding='utf-8').replace('Sus 36 controles focales pasan; las pruebas completas de memoria están en marcha. Se preparó517 para comprobar el efecto real después de validarlas.','Sus36 controles focales y1962 pruebas de memoria pasan, sin omisiones. Fast y Release también pasan, sin advertencias ni errores. Se preparó517 para comprobar el efecto real.').replace('Hay204 candidatos potenciales; ninguno certificado ni ejecutado para aceptación. Faltan contexto, entrenamiento y actualización de exposición.','De204 candidatos potenciales, el cruce518 con15510 filas de tres conjuntos heredados encontró92 coincidencias de entrenamiento/evaluación. Quedan112 sin coincidencia en ese cruce,101 con original completo; esto aún no acredita frescura. Ninguno está certificado ni ejecutado para aceptación. Faltan contexto, otras fuentes, actualización de exposición y mensajes de mezcla natural sin ese solapamiento.')
report.write_text(text,encoding='utf-8')
print('516 closed with owners and Fast green; 517 ready; entire C03 remains active.')
