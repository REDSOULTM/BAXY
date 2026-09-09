from pathlib import Path
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
report=base/'PRUEBAS_AEC177_178.md'
report.write_text(report.read_text(encoding='utf-8')+'''
## Resultado178

Reintento84605 exit0; evaluación55442 exit0, diez filas (cinco controles/dos etapas).
La referencia menor mantiene0bloques de habla residual en ambos ecos y silencio,
pero la mezcla sigue «Exactly.» en Parakeet crudo/normalizado. No cumple palabras
cercanas; no adoptada y no barrido de ganancias. La fuente CMake178 y ambas
salidas de build quedan conservadas; la biblioteca nativa176 no se recompiló.
Cambio de estrategia179: contraste neuronal DTLN, no otra configuración AEC3.
''',encoding='utf-8')
text='''# C03 — contraste neuronal DTLN-AEC —179–181

DTLN elimina los dos ecos del panel y conserva la frase cercana sola ante
Parakeet. La mezcla todavía presenta discrepancias/pérdidas entre observadores;
no se acredita fidelidad completa ni se adopta/promueve un motor nuevo.
No se cambiaron código de producto, umbrales, voz, LLM ni runtime registrado.

## Herencia y alternativa

Speex173 conserva2/4 cortes físicos. WebRTC174/178 elimina eco offline pero pierde
palabras cercanas: PRUEBAS_AEC173_175.md,PRUEBAS_AEC176.md,PRUEBAS_AEC177_178.md.
Inventario histórico buscado por DTLN/eco/AEC sin título específico nuevo;
PRUEBAS_ECO126_128.md ya descartó prolongar ventana/cambiar umbral de correlación.

[DTLN-AEC del autor](https://github.com/breizhn/DTLN-aec/tree/9d24e128b4f409db18227b8babb343016625921f),
revisión9d24e128b4f409db18227b8babb343016625921f, consultada2026-09-07. Código MIT,
licencia copiada. Se descarga primero128 (1,8M parámetros;7.273.612bytes); al
fallar mezcla a coste bajo,512 (10,4M;41.521.804bytes), el modelo presentado por
el autor al AEC Challenge. No se descarga256. Git blobs verificados y SHA256
de cada archivo/modelo en DOWNLOADS. No datos privados enviados fuera.

LiteRT2.2.0, wheel CPython312 Windows x6417.914.562bytes, SHA
86815ff3378ac9fa4bb5548bcede1be7d050bd59a8ebaf1c056b7aef69fedcee.
Extraída sólo en D:/BAXYRuntime/experiments/voice/dtln179/python, reutilizada180.
Interpreter CPU1/XNNPACK carga y asigna tensores; sin instalar TensorFlow ni
dependencias de2020 del autor. Runtime registrado no alterado.

## Método

Se ejecuta process_file extraído por AST del run_aec.py del autor, sin cambiar
su cálculo. Sólo sf.read/write son I/O en memoria; no se ejecuta su recorrido
de directorios, importTensorFlow ni cambio global de CUDA. Dos estados nuevos
por control, FFT/máscara/IFFT/overlap-add originales,512ventana/128salto.
Su padding/corte final se conserva; NO se ha demostrado equivalencia de un
adaptador en vivo512→128 ni latencia/finalización física.

Mismos cinco controles174, señales float32 por SHA en INPUTS, mismo detector
y criterios VAD0,5/energía0,004/floor1,8/consecutivos. Sin guard crudo: candidatos
máximos, no cancelación de producto. Guard no puede crear candidato si hay cero.
Los controles127/129 tienen alineación aproximada;149 son arrays ADC nativos.

Parakeet registradoCPU6/beam8,sin hints, mismo recorte131, PCM16 crudo y normalizado
a pico0,8.181 Nemotron3.5 ya instaladoCPU6/greedy/auto,mismo recorte,0,66s de
silencio final,crudo/normalizado. ASR es observación, no oyente humano infalible.

## Resultados179/180

| Modelo | Caso | Bloques habla | Candidatos | Mayor secuencia | ms por8ms | Parakeet crudo | Normalizado |
|---|---|---:|---:|---:|---:|---|---|
'''
for stage,units in [(179,128),(180,512)]:
    rows=json.loads((base/f'astra-dtln{stage}/RESULTS.json').read_text(encoding='utf-8'))
    assert len(rows)==5
    for r in rows:
        words=[w['text'] or '(vacío)' for w in r['transcripts']]
        text+=f"| {units} | {r['case']} | {r['speechFrames']} | {r['qualifiedFramesWithoutGuard']} | {r['maxConsecutiveWithoutGuard']} | {r['processingMsPer8msHop']:.3f} | {words[0] if words else 'no ejecutado'} | {words[1] if words else 'no ejecutado'} |\n"
text+='''
179 sesión51502 exit0;180 sesión29193 exit0. El coste medio no certifica p99
ni tiempo real con LLM/audio/UI. RSSdelta primer caso~15MB128 y~85MB512 incluye
buffers; no es consumo final combinado. No nueva medición VRAM de producto.

## Observador181

| Modelo | Caso | Normalizado | Nemotron |
|---|---|---|---|
'''
for r in json.loads((base/'astra-observe181/RESULTS.json').read_text(encoding='utf-8')):
    text+=f"| {r['units']} | {r['case']} | {r['normalized']} | {r['text'] or '(vacío)'} |\n"
text+='''
181 sesión71768 exit0. Nemotron crudo también pierde palabras del control cercano
solo que Parakeet recupera completo. Por ello no atribuir cada desacuerdo al AEC.
La normalización mejora observación, pero no sustituye éxito crudo del producto.
Se conserva que Parakeet de mezcla128 omite palabras y512 produce «puedar»;
no declarar esas lecturas frases fieles ni convertirlas en textos esperados.

## Decisión y siguiente acción

No nueva ganancia AEC3 ni colección de modelos. DTLN constituye un candidato
de desarrollo por rechazo de eco/coste, no sustitución aceptada. Antes de otra
prueba física, preparar un adaptador experimental continuo del cálculo del autor
y verificar paridad/latencia con179/180:128divide512 sin introducir padding por
llamada. Conservar el fallo de mezcla y contrastar el ciclo real de interrupción
(la voz propia se cancela al detectar habla, no sigue sonando todo el clip).
Ese contraste no borra el control de doble habla sostenida ni acredita humano.
No cambiar producción hasta tener mejora semántica y garantías conservadas.

C03 EN_CURSO: fuente172 vigente,130tests/Fast verdes;173 físico2/4 cortes.
Reserva100 sin congelar/ejecutar, ocho rutas finales, voz/ingreso/UI,averías,
promoción/regresión/continuidadC04–C09,Full y publicación siguen pendientes.
Sin procesos propios activos ni modificaciones de volumen durante174–181.
'''
(base/'PRUEBAS_DTLN179_181.md').write_text(text,encoding='utf-8')
out=base/'astra-gain178'
for name in ['c03-gain178-build.log','c03-gain178-build-retry.log','c03-gain178-evaluate.log']:
    (out/name).write_bytes((Path(os.environ['TEMP'])/name).read_bytes())
for name in ['CMakeLists.txt','bindings/webrtc_audio_bindings.cpp']:
    before=Path('D:/BAXYRuntime/experiments/voice/webrtc176/source')/name
    after=Path('D:/BAXYRuntime/experiments/voice/webrtc178/source')/name
    (out/(Path(name).name+'.patch')).write_text(''.join(difflib.unified_diff(before.read_text(encoding='utf-8').splitlines(True),after.read_text(encoding='utf-8').splitlines(True),fromfile='176/'+name,tofile='178/'+name)),encoding='utf-8')
for stage in [179,180]:
    (base/f'astra-dtln{stage}'/f'c03-dtln{stage}-evaluate.log').write_bytes((Path(os.environ['TEMP'])/f'c03-dtln{stage}-evaluate.log').read_bytes())
(base/'astra-observe181/c03-observe181.log').write_bytes((Path(os.environ['TEMP'])/'c03-observe181.log').read_bytes())
groups={
 'astra-timing177':['PREREG.json','RESULTS.json','INPUT_INDEX.json'],
 'astra-gain178':['PREREG.json','RESULTS.json','BUILD.json','PRIVATE_INDEX.json','c03-gain178-build.log','c03-gain178-build-retry.log','c03-gain178-evaluate.log','CMakeLists.txt.patch','webrtc_audio_bindings.cpp.patch'],
 'astra-dtln179':['PREREG.json','DOWNLOADS.json','RUNTIME_METADATA.json','INPUTS.json','RESULTS.json','PRIVATE_INDEX.json','COMPLETE.json','c03-dtln179-evaluate.log'],
 'astra-dtln180':['PREREG.json','DOWNLOADS.json','INPUTS.json','RESULTS.json','PRIVATE_INDEX.json','COMPLETE.json','c03-dtln180-evaluate.log'],
 'astra-observe181':['PREREG.json','RESULTS.json','c03-observe181.log']}
public=[base/folder/name for folder,names in groups.items() for name in names]
public += [base/n for n in ['PRUEBAS_AEC177_178.md','PRUEBAS_DTLN179_181.md']]
public += [root/'scratchpad'/n for n in ['c03-timing177.py','c03-prepare178.py','c03-prepare-evaluation178.py','c03-evaluate178.py','c03-prepare179.py','c03-evaluate179.py','c03-prepare180.py','c03-evaluate180.py','c03-observe181.py']]
private=[]
for folder in ['astra-gain178','astra-dtln179','astra-dtln180']:
    for row in json.loads((base/folder/'PRIVATE_INDEX.json').read_text(encoding='utf-8')):
        assert sha(Path(row['privatePath']))==row['sha256'];private.append(row)
old=json.loads((base/'TRAMO172_176_PINS.json').read_text(encoding='utf-8'))
assert all(sha(root/r['path'])==r['sha256'] for r in old['public'])
assert all(sha(Path(r['privatePath']))==r['sha256'] for r in old['private'])
save(base/'TRAMO177_181_PINS.json',{'public':[{'path':str(p.relative_to(root)),'sha256':sha(p),'bytes':p.stat().st_size} for p in public],'private':private})
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name
    archive=base/name.replace('.md','_HISTORICO_HASTA176.md')
    assert not archive.exists();archive.write_bytes(p.read_bytes())
handoff='''# Handoff C03 —181 —2026-09-07 — EN_CURSO

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, continuación01a074f6-9e0e-7fb3-8282-a6b706198a7e.
Goal activo completo; Goal-c03,HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49.
Sin commit/push/main/subagentes. Conservar WIP y evidencia privada/pública.

## Estado y decisión

Fuente172 vigente (contador barge consecutivo/una emisión);130pass0skips7,36s,
Fast55364exit0,Release2,73s0avisos/errores.173 físico aún2/4cortes.164 precarga
SciPy antes lectorJSONL corrigió bloqueo; UI166 tres horas veraces~1s y3499,5MiB
VRAM, pero audio no aceptado. No nuevo Full ni promoción durante174–181.

AEC3 aislado174: eco149/1270VAD pero mezcla pierde palabras.176 exporta lineal,
finalbitidéntico174; residual pierde más, lineal tampoco conserva todo/dejaeco.
177: near empieza35msantes de sonido de referencia (speaking no era sonido).
178 ganancia0,1 inspirada en fieldtrialupstream no recupera palabras: NO adoptar
ni barrer ganancias. PRUEBAS_AEC173_175.md/176.md/177_178.md y pins.

179 DTLN128 y180 DTLN512, fuente del autor9d24e128b4f409db18227b8babb343016625921f,
LiteRT2.2.0 CPU1/XNNPACK aislado; algoritmo process_file sin cambio, sóloI/O.
Ambos0VAD en2ecos/silencio; Parakeet recupera near-only, mezcla sigue discrepante.
128~0,3ms/8ms;512~2,5–2,9ms/8ms.181Nemotron recupera más normalizado pero también
falla near-only crudo; no observador infalible. PRUEBAS_DTLN179_181.md tiene todos
los textos/criterios. Ninguno promovido ni aceptado como sustitución de Speex.

## Procesos, evidencia y entorno

Todos recogidos: build1769568/eval83450,build17818707fallóincludes/retry84605pass,
eval17855442,17951502,18029193,18171768 terminaron. Ningún proceso propio activo.
TRAMO172_176_PINS.json43públicos40privados verificado; TRAMO177_181_PINS.json nuevo.
No editar informes/scripts fijados. CHECKPOINT/HANDOFF_HISTORICO_HASTA176 conserva
historia y rutas de texto/UI/reserva. Datos no se enviaron fuera; no audiofísico174–181.
Runtime: C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.
`py` es313 sinpytest; sólo py main.py para UI. Manifiesto registrado13b971b3… intacto.
DTLN179: D:/BAXYRuntime/experiments/voice/dtln179 (128,LiteRT,run_aec.py/LICENSE).
DTLN180: D:/BAXYRuntime/experiments/voice/dtln180 (512, mismo runtime179).
WebRTC176/178: D:/BAXYRuntime/experiments/voice/webrtc176 y webrtc178.

## Siguiente acción

Abrir run_aec.py179:57–140 y c03-evaluate179.py; adaptar experimentalmente el
streaming512→128 y verificar continuidad/paridad/latencia con señales179/180.
No padding por llamada. Luego contrastar interrupción cerrando salida real,
conservando fallo de mezcla sostenida; no declarar aceptación humana por síntesis.
No repetir UI, modelos o filtros sin una hipótesis distinta y criterio mantenido.

## Cierre restante íntegro

Audio/entrada humana/wake (App permite manifiesto no aprobado), ocho rutas finales,
100humanos frescos congelados y100/100 (742pool/239revisados;100NOcongelados),
averías/recuperación,UI/runtime/4GB, promoción/regresión/continuidadC04–C09,Full
entero y publicación fuera main. Tres ingleses ya confirmados: «Son turnos validos»;
no preguntar de nuevo. C03_ASTRA_AUTORIDAD.md y C03_RESPUESTA_VERAZ.md mandan.
'''
(base/'HANDOFF.md').write_text(handoff,encoding='utf-8')
(base/'CHECKPOINT.md').write_text(handoff.replace('# Handoff C03','# CHECKPOINT C03'),encoding='utf-8')
p=base/'RELEVO_ACTIVO.json';d=json.loads(p.read_text(encoding='utf-8'))
d.update(goalStatus='active',confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='181 completo. AEC3 default/0,1 descartados como sustitución; DTLN128/512 rechazoeco y near-only, mezcla discrepante, no adoptados. Fuente172 vigente.',continuation='Adaptador experimental continuo DTLN512→128 con paridad/latencia, antes de ciclo físico de interrupción. Sin procesos propios activos. C03 íntegro.')
save(p,d)
print(json.dumps({'publicPins':len(public),'privatePins':len(private),'priorPinsVerified':True,'goal':'active'}))
