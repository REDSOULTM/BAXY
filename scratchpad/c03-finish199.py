"""Preserve completed195-199 evidence and current continuation, no product changes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import collections

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
local=Path(os.environ['LOCALAPPDATA'])/'BAXY'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
prior=read(base/'TRAMO194_PINS.json')
assert all(sha(root/r['path'])==r['sha256'] for r in prior['public'])
assert all(sha(Path(r['privatePath']))==r['sha256'] for r in prior['private'])
prereg194=read(base/'astra-ui194/PREREG.json')
assert all(sha(root/p)==h for p,h in prereg194['sourceFiles'].items())
assert sha(Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json')==prereg194['registrationSha256']
for folder in ['astra-human195','astra-human197','astra-human-aec198','astra-observe-human199']:
    assert (base/folder/'COMPLETE.json').exists()
search=read(base/'astra-find-audio196/RESULTS.json')
assert search['remainingDirectories']==61
rows=read(base/'astra-observe-human199/RESULTS.json');assert len(rows)==48
inputs=read(base/'astra-human195/DOWNLOADS.json');assert len(inputs)==4
private=[]
for row in inputs:
    p=Path(row['asset']);assert sha(p)==row['sha256'];private.append(p)
assets=Path('D:/BAXYRuntime/experiments/voice/fleurs195')
private.extend(assets/f'{config}-test.tsv' for config in ['es_419','en_us'])
for row in read(base/'astra-human-aec198/RESULTS.json'):
    p=Path(row['privateOutput']);assert sha(p)==row['sha256'];private.append(p)
search_private=local/'C03-find-audio196-private'
private.extend(search_private/name for name in ['files.jsonl','FOLDERS.json','ERRORS.json','FRONTIER.json','LIVE.json'])
legacy=Path('D:/Perfil/Escritorio/ETC/Programacion/Probando Gemma 4/gemma4_agent/voice/tests')
legacy_names=['Grabación (2).m4a','Grabación (2).wav','testaudio_full.wav','testaudio_groundtruth_report.md','testaudio_groundtruth_aligned.json','testaudio_groundtruth_full.json','testaudio_v2_expected.json']
private.extend(legacy/name for name in legacy_names)
legacy_index=[{'privatePath':str(legacy/name),'sha256':sha(legacy/name),'bytes':(legacy/name).stat().st_size} for name in legacy_names]
save(search_private/'LEGACY_RECORDING_INDEX.json',legacy_index);private.append(search_private/'LEGACY_RECORDING_INDEX.json')
wav_same=legacy_index[1]['sha256']==legacy_index[2]['sha256']
folders=read(search_private/'FOLDERS.json')
capture_count=sum(row['audioFiles'] for row in folders if 'gemma4_agent\\data\\voice_recordings\\' in row['path'])
assert capture_count==1012
report='''# C03 — controles humanos y búsqueda local —195–199

Sin cambios de producto, AEC, umbrales, modelo o registro. Fuente192 y prueba
UI194 siguen intactas. C03 EN_CURSO; no Full durante reparación.

## Grabaciones públicas195

Cuatro WAV originales de Google FLEURS, dos es_419 y dos en_us, test,
revisión70bb2e84b976b7e960aa89f1c648e09c59f894dd. Atribución: Conneau et al.,
FLEURS (2022), licencia CC-BY-4.0. [Dataset](https://huggingface.co/datasets/google/fleurs)
y [paper](https://arxiv.org/abs/2205.12446). No datos locales enviados.

Primer acceso falló por imports requests/soundfile ausentes, sin instalar nada.
La API rows y first-rows devolvió500 por grupo Parquet de703MB y límite300MB.
Se conservó ese intento y se fijó PREREG-TAR antes de obtener audio: dos IDs de
transcripción distintos por idioma, en orden del tar del autor, duración<=20s.
Lectura acotada a100miembros/64MiB comprimidos. No elección según acierto de ASR.
Se guardaron cuatro WAV float32/16k originales, sin normalizar ni recodificar;
dos TSV y hashes, 12,84/9,72/10,56/8,76s. Nunca son reserva Carter→BAXY.

## Búsqueda local196, autorizada por el dueño

Se priorizaron Probando Gemma4, BAXY, Carter OS AI y FunctionGemma y se amplió
a C:/ y D:/. Inventario de nombres/metadatos; ningún audio subido ni proyecto
anterior modificado. Se excluyó el árbol actual, Windows, papelera, junctions,
cachés indicadas y capturas C03 ya conocidas. Duración300s, sesión88361exit0.
1.615.235 archivos examinados,471.912 archivos con extensión de audio en3.252
carpetas; la mayoría de esa cifra no acredita grabación humana. Hubo7 errores
de acceso y quedaron61 directorios en la frontera privada. No es búsqueda
completa de todo el disco. El inventario y sus rutas personales quedan privados.

Hallazgos en Probando Gemma4:1.012 archivos de audio del registro de voz de
23–25junio,338 muestras en wake_positives_real,454 en wake_false_positives y
la grabación de292,842854s en gemma4_agent/voice/tests. Un sidecar de captura
confirma16kHz,3,872s, razón eos_silence y event_id; esto prueba captura, no quién
habló ni que fuera voz humana en lugar de reproducción. Los manifests históricos
real_mic/real_es buscados en las dos raíces candidatas no existen allí.

«Grabación (2).m4a» tiene metadato creation_time2026-05-18T16:44:35Z. El reporte
asociado atribuye su transcripción a faster-whisper large-v3: el rótulo ground
truth no la convierte en anotación humana. Reporte y JSON alineado incluso
discrepan en algunos textos. v2_expected contiene105wakes/103marcas de comando.
Se preguntó al dueño si es una grabación suya; respuesta pendiente al registrar.
No se necesita esa respuesta para continuar diagnósticos públicos. No ampliar
su admisión previa de tres turnos ingleses a este audio ni a otras capturas.
'''
report+=f'\nLos WAV Grabación(2) y testaudio_full son idénticos por SHA256: {wav_same}.\n'
report+='''
## Baseline197 y comparación198–199

197:8 lecturas completas, cuatro originales sin cambio de ganancia, Parakeet
CPU6/beam8 y Nemotron CPU6/greedy/flush0,66s. Sin pistas textuales; errores del
original conservados. Sesión46684exit0. El baseline no declara4/4 perfectos.

198: cada grabación se escala una vez a RMS0,01 y se inserta un segundo después
del primer bloque de referencia187 RMS>=20PCM: muestra31872. Se conserva el
micrófono y referencia exactos de187; referencia continua. Una condición sólo
voz usa referencia cero; otra suma el eco físico grabado. Raw/Speex/DTLN128,
estado nuevo por condición, sin barrido de ganancia/retardo.24señales conservadas;
sesión1037exit0. El VAD y máscara speaking son controles offline, no la captura
con resets de segmentación o la reproducción posterior a una interrupción real.

199:48lecturas, ambos reconocedores sobre las24ventanas fijadas antes. Sin
normalización adicional ni texto esperado. Sesión27801exit0. Tabla de errores
superficiales de palabra; puntuación/caja ignoradas, números y homófonos no
normalizados. No es una tabla de pass/fail semántico.

| Audio | Motor AEC | Parakeet sólo voz | Parakeet mezcla | Nemotron sólo voz | Nemotron mezcla |
|---|---|---:|---:|---:|---:|
'''
for human in range(4):
    for engine in ['raw','speex','dtln128']:
        counts=[]
        for recognizer,condition in [('parakeet','near_only'),('parakeet','mixed'),('nemotron','near_only'),('nemotron','mixed')]:
            r=next(r for r in rows if r['human']==human and r['engine']==engine and r['recognizer']==recognizer and r['condition']==condition)
            counts.append(f"{r['wordEdits']}/{r['referenceWords']}")
        report+=f"| {inputs[human]['config']} ID{inputs[human]['id']} | {engine} | "+' | '.join(counts)+' |\n'
report+='''
Lecturas literales completas y orden en astra-human197/RESULTS.json y
astra-observe-human199/RESULTS.json; datos/ventanas/payloads de referencia en sus
PREREG. No se descarta ningún intento ni se elige el observador más favorable.

Hallazgo decisivo: DTLN128 no domina a Speex. En el segundo audio inglés mezclado,
ambos observadores pierden parte del inicio con DTLN; Parakeet con Speex conserva
el inicio. En el primer inglés DTLN sí mejora la mezcla. En voz sola, Parakeet
devuelve vacío con Speex para ese primer inglés, pero Nemotron recupera la frase:
no afirmar borrado físico de audio a partir de una transcripción vacía.
Persisten degradaciones y desacuerdos. No promover DTLN por estos controles ni
repetirlos buscando otra combinación favorable. El fallo físico183 permanece.

## Continuación

Cambia la siguiente acción: ya hay candidatos de grabación local con registros y
cuatro controles humanos públicos fijados; no hacen falta más descargas para
diagnosticar. Verificar procedencia de Grabación(2) y sus segmentos sin dar por
humanos sus ground-truth automáticos. Para el eco, localizar en los mismos PCM
conocidos qué parte de habla/eco conserva cada salida antes de otro cambio de
motor o detector. Contrastar un mecanismo concreto, no acumular tamaños/modelos.

Pendientes íntegros: fallo acústico183, activación/entrada humana aprobadas,
ocho rutas finales,100humanos reservados congelados y100/100, averías/recuperación,
UI/runtime/4GB, promoción/regresión/instalación/continuidadC04–C09, Full/publicación.
Ningún proceso propio queda pendiente en195–199. No commit/push/main/subagentes.
'''
(base/'PRUEBAS_HUMANOS195_199.md').write_text(report,encoding='utf-8')
public=[base/'PRUEBAS_HUMANOS195_199.md']
for folder,names in {
 'astra-human195':['PREREG.json','PREREG-TAR.json','DATASET.json','DOWNLOADS.json','COMPLETE.json','es_419-TRANSFER.json','en_us-TRANSFER.json'],
 'astra-find-audio196':['PREREG.json','RESULTS.json'],
 'astra-human197':['PREREG.json','RESULTS.json','COMPLETE.json'],
 'astra-human-aec198':['PREREG.json','RESULTS.json','COMPLETE.json'],
 'astra-observe-human199':['PREREG.json','RESULTS.json','COMPLETE.json'],
}.items():public.extend(base/folder/name for name in names)
scripts=['c03-fleurs195.py','c03-fleurs195-tar.py','c03-find-audio196.py','c03-human197.py','c03-human-aec198.py','c03-observe-human199.py','c03-finish199.py']
public.extend(root/'scratchpad'/name for name in scripts)
logs=['c03-fleurs195.log','c03-fleurs195-retry.log','c03-fleurs195-stdlib.log','c03-fleurs195-tar.log','c03-find-audio196.log','c03-human197.log','c03-human-aec198.log','c03-observe-human199.log']
logdir=base/'astra-logs195_199';logdir.mkdir(exist_ok=False)
for name in logs:
    p=logdir/name;p.write_bytes((Path(os.environ['TEMP'])/name).read_bytes());public.append(p)
save(base/'TRAMO195_199_PINS.json',{'public':[{'path':str(p.relative_to(root)),'sha256':sha(p),'bytes':p.stat().st_size} for p in public],
    'private':[{'privatePath':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in private]})
for name in ['CHECKPOINT','HANDOFF']:
    source=base/f'{name}.md';backup=base/f'{name}_HISTORICO_HASTA194.md'
    assert not backup.exists();backup.write_bytes(source.read_bytes())
note='''# C03 — checkpoint199 — EN_CURSO —2026-09-07

Tarea01a07974-2a33-7ed3-ba87-2436944e8115; continúa01a074f6-9e0e-7fb3-8282-a6b706198a7e.
Goal íntegro activo, Goal-c03, HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49.
Sin commit/push/main/subagentes; conservar WIP/evidencia privada e histórica.

## Fuente actual y UI

Fuente192 vigente: eventos wake/dudoso pasan por hechos y compositor/cola
existentes, sin dos TTS fijos; avisos obsoletos descartados.113Python/16.NET,
0skips y Fast verdes.164 corrige precarga SciPy;172 contador barge consecutivo.
UI194 tres casos correctos, hora13:05 verificada en Core, aviso antiguo ausente.
Monitor51134exit0/cleanup0, GPU3480,15MiB,RAM5326,41MiB. No aceptación acústica.
PRUEBAS_UI194/TRAMO194_PINS íntegros; fuente/registro idénticos al prereg194.
Qwen3.5 sigue override, registro Qwen3-4B2507 intacto13b971b3…; Speex sigue AEC.

## Nuevo195–199

195 cuatro WAV humanos públicos FLEURS ES/EN fijados con transcripción/licencia,
sin envío de datos locales. API falló; tar autor revisión70bb2e… leído acotado.
197 ocholecturas originales completas, con errores ASR conservados.
198 veinticuatro señales: cuatro voces RMS0,01 × sólo voz/mezcla eco187 ×
raw/Speex/DTLN128. Inicio31872, misma referencia/mic187, sin barrido ni reproducción.
199 cuarenta y ocholecturas completas. DTLN no domina: mejora primer inglés,
pero pierde inicio del segundo inglés mezclado; Speex/Parakeet lo conserva.
Parakeet vacío en primer inglés sólo voz/Speex NO prueba corte: Nemotron recupera.
No promover ni repetir buscando pase. PRUEBAS_HUMANOS195_199 y TRAMO195_199_PINS.

## Búsqueda local autorizada por dueño

196 búsqueda por nombres en proyectos previos/C:/D: durante300s:1.615.235archivos,
471.912extensiones audio,3.252carpetas. No equivale a ese número de voces humanas.
7errores,61directorios pendientes; exclusiones explícitas. Índice privado:
LOCALAPPDATA/BAXY/C03-find-audio196-private/{files.jsonl,FOLDERS,ERRORS,FRONTIER}.json
(files es JSONL, los otros JSON). No recorrer de nuevo: usar índice/frontier.
Probando Gemma4 tiene1.012capturas fechadas,338wake_positives_real,454negativas.
gemma4_agent/voice/tests/Grabación(2).m4a:292,842854s; WAV y testaudio_full sellados.
Reporte ground-truth viene de Whisper, no humano;105wakes/103marcas v2_expected.
Pregunta opcional sobre quién grabó este audio pendiente; no bloqueo del goal.
No confundir con los tres ingleses YA admitidos por dueño ni pedirlos otra vez.
No escribir en proyectos anteriores. No contar estos audios como reserva100.

## Procesos, validación y siguiente

Todos recogidos exit0: búsqueda88361,baseline46684,AEC1037,observación27801.
Sin procesos propios activos.195–199 no cambian producto; no Full durante reparación.
Tramo anterior fue progreso: cierre UI194/evidencia; actual añade controles y
fuentes reales que cambian la próxima acción. Sin bloqueo externo ni cierre.

Siguiente: verificar procedencia/anotación del audio local si llega respuesta;
para AEC usar PCM198 ya fijados para localizar conservación de voz/eco antes de
otro motor/detector. No más descarga de corpus: cuatro controles públicos y
candidatos locales disponibles. Fallo físico183 y mezcla129 siguen abiertos.
No usar scripts que fijan fuente172; 191 ya resolvió lectura inglesa187 del ASR.

Pendientes completos: audio/entrada humana/wake aprobado, ocho rutas finales,
100humanos frescos congelados y100/100(742pool/239revisados;100NOcongelados),
averías/recuperación,UI/runtime/4GB,promoción/regresión/instalación/continuidadC04–C09,
Full entero y publicación fuera main. Autoridades C03_ASTRA_AUTORIDAD y
C03_RESPUESTA_VERAZ. Detalle anterior en CHECKPOINT/HANDOFF_HISTORICO_HASTA194.
'''
for name in ['CHECKPOINT.md','HANDOFF.md']:(base/name).write_text(note,encoding='utf-8')
state_path=base/'RELEVO_ACTIVO.json';state=read(state_path)
state.update(goalStatus='active',confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='199: búsqueda local autorizada y controles humanos ES/EN;24señales/48lecturas. DTLN no domina. Fuente192/registro intactos;194sellado.',continuation='Usar índices196 y PCM198 ya fijados; procedencia de Grabación(2) pendiente opcional. Fallo acústico183 abierto. Sin procesos activos; conservar alcance completo.')
save(state_path,state)
print(json.dumps({'publicPins':len(public),'privatePins':len(private),'legacyWavsIdentical':wav_same,'priorPinsVerified':True,'sourceUnchanged':True,'goal':'active'}))
