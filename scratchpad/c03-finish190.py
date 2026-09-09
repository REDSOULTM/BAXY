"""Pin completed182–190 evidence and leave a current, bounded handoff."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import psutil

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
local=Path(os.environ['LOCALAPPDATA'])/'BAXY'
def sha(path):
    with path.open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not any(p.info['name'] in {'Baxy.exe','llama-server.exe','piper.exe'} for p in psutil.process_iter(['name']))
source=json.loads((base/'astra-sidecar187/PREREG.json').read_text(encoding='utf-8'))
assert all(sha(root/path)==digest for path,digest in source['sourceFiles'].items())
report='''# C03 — variabilidad física y señales reproducibles —185–190

No hay nuevo arreglo de producto ni aceptación de audio. DTLN128 se mantiene
experimental:183 cortó la primera hora española;185 y187 no registraron cortes.
Esto no borra183 ni prueba robustez.187 conserva además el PCM generado y la
señal exacta del cancelador;188 reproduce el cálculo sin diferencia alguna.

## Ejecuciones y limpieza

185 driver96589/captura13341 recogidos exit0.79,55s de captura y56,422s de
conductor. Cero overflows; hilos detenidos y endpoint restaurado a0/mutedtrue.
Snapshot previsto sólo tras primer barge_in: no existe porque no hubo evento.
El analizador preparado para ese snapshot no se ejecutó y fue retirado.

187 driver52688/captura89539 recogidos exit0.76,31s de captura y55,797s de
conductor. Cero overflows; hilos detenidos y restauración exacta. Trace acotado
en memoria,1249bloques/39,968s, guardado al salir. Observación altera scheduling;
no se atribuye a ella la diferencia respecto a183/185. Se conservan cuatro PCM
Piper originales con texto, tasa22050Hz, modelo y hora; no se regeneraron.

186 sesión30401 y189 sesión2240 recogidas exit0:16lecturas por ejecución.
Parakeet registrado CPU6beam8 sin pistas; crudo y pico0,8. Ventanas por UTC
pareado a estado con margen1s, mismas limitaciones de primer sonido real.

## Lecturas literales de audio físico

Las columnas son observaciones de reconocimiento, no respuestas nuevas de BAXY.
Se conserva lo incorrecto y vacío; recuperar una variante no convierte todo en pass.

| Ensayo | Salida | Canal | Crudo | Normalizado |
|---|---:|---|---|---|
'''
for stage in [186,189]:
    rows=json.loads((base/f'astra-observe{stage}/RESULTS.json').read_text(encoding='utf-8'))
    assert len(rows)==16
    for output in range(1,5):
        for channel in ['microphone','loopback']:
            pair=[r for r in rows if r['output']==output and r['channel']==channel]
            report+=f"| {stage-1 if stage==186 else 187} | {output} | {channel} | {pair[0]['text'] or '(vacío)'} | {pair[1]['text'] or '(vacío)'} |\n"
report+='''
Salidas enviadas:1«¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?»;
2«Son las10:55.»;3«It is10:56.»;4«Son las10:56.» (literales con espacios
exactos en PREREG185/187).185 recupera cada contenido en alguna lectura;
187 inglés no se recupera completo. Esto no equivale a detectar un corte.

## Reproducción188

Sesión21835 recogida exit0.1249bloques DTLN128 bitidénticos a187; probabilidades
VAD también idénticas en1249/1249. Referencia continua verificada por solapamiento.
128 y512 dan cero bloques de habla sobre esta señal de eco. Coste512 p99
19,38ms por32ms, máximo32,42ms;128 p99 2,69ms. No certifica coste combinado.
No se acreditan doble habla ni interrupciones contrafactuales: máscara speaking
congelada de187. Los fallos de mezcla129/179–181 siguen pendientes.

El [artículo DTLN-AEC](https://arxiv.org/html/2010.14337), secciones2.4 y4,
consultado2026-09-07, describe entrenamiento con retardos de10–100ms y una
mayor dificultad al separar voces parecidas. No exige alinear a retardo cero.
Por ello no hay fundamento aquí para un barrido de desplazamientos ni para
atribuir automáticamente el fallo de mezcla al retardo acústico de52ms.

## Origen frente a reproducción190

Comando compare190 terminó exit0: ocho lecturas sobre cuatro PCM originales,
sin pistas, con1s de silencio a cada lado; amplitud original y ajustada mediante
mínimos cuadrados al loopback. Nada se sintetizó otra vez. Datos en
astra-compare190; todos los bloques de200ms y lecturas se conservan.

| Salida | Parakeet original Piper | Original a ganancia estimada de loopback | Correlación global |
|---|---|---|---:|
'''
for row in json.loads((base/'astra-compare190/RESULTS.json').read_text(encoding='utf-8')):
    texts=[r['text'] or '(vacío)' for r in row['sourceTranscripts']]
    report+=f"| {row['output']} | {texts[0]} | {texts[1]} | {row['wholeWaveCorrelation']:.4f} |\n"
report+='''
El inglés ya se reconoce como «It is ten.» desde el PCM generado, antes de
altavoces/AEC. Esto impide atribuir esa omisión de ASR al cancelador o a otro
corte. No demuestra por sí solo que Piper omita los minutos: falta un observador
independiente de la misma onda. Correlaciones0,48–0,70 y diferencias por bloque
no prueban igualdad de reproducción; ajuste global no corrige deriva/filtrado.
No se cambia timeout, volumen ni pronunciación sin localizar la primera pérdida.

## Herencia para controles humanos y pendientes

Se consultó biblioteca/01_INVENTARIO.md por corpus/voz/STT. El reporte histórico
gemma4-agent/documentacion/03_voz_stt/research/baseline_real_voice.txt declara
84clips RED y180terceros, con WER elevado; REPORTE_NOCHE_STT_PARAKEET_2026_05_23.md
remite a scripts/stt_real_voice_eval.py y download_fleurs_es.py. No se han
localizado/verificado sus audios; no se acredita procedencia por el título ni
se cuentan como reserva100. barge_in.md es diseño histórico, no instrucción;
no se adopta su umbral500ms ni su propuesta de omitir audio durante voz.

Siguiente: observador independiente sobre PCM187 congelado y loopback189 para
distinguir pronunciación de error de reconocimiento; no repetir frases físicas
ni descargar otro cancelador. Conservar también fallo183 y mezcla129.
Fuente172 y runtime registrado intactos, sin Full nuevo/commit/push. C03 activo
íntegro: ocho rutas finales,100humanos congelados y100/100, averías, UI/voz/wake,
4GB, promoción reproducible, continuidadC04–C09, Full y publicación.
'''
(base/'PRUEBAS_VOZ185_190.md').write_text(report,encoding='utf-8')
groups={'astra-stream182':['PREREG.json','RESULTS.json','COMPLETE.json']}
private_rows=[]
for stage in [183,185,187]:
    folder=f'astra-sidecar{stage}'
    groups[folder]=['PREREG.json','RUNTIME_CONFIG.json','RESULTS.json','CLEANUP.json','INDEX.json','AUDIO_READY.json','AUDIO_RESULT.json']
    for row in json.loads((base/folder/'INDEX.json').read_text(encoding='utf-8')):
        assert sha(Path(row['privatePath']))==row['sha256'];private_rows.append(row)
    audio=json.loads((base/folder/'AUDIO_RESULT.json').read_text(encoding='utf-8'))
    assert audio['threadsStopped'] and audio['restoredExactly']
    assert all(r['overflows']==0 for r in audio['streams'].values())
    for row in audio['streams'].values():
        path=Path(row['privatePath']);assert sha(path)==row['sha256']
        private_rows.append({'privatePath':str(path),'sha256':row['sha256'],'bytes':path.stat().st_size})
for stage in [184,186,189]:groups[f'astra-observe{stage}']=['PREREG.json','RESULTS.json','COMPLETE.json']
for folder in ['astra-replay188','astra-compare190']:groups[folder]=['PREREG.json','RESULTS.json','COMPLETE.json']
for row in json.loads((base/'astra-replay188/RESULTS.json').read_text(encoding='utf-8')):
    path=Path(row['privateOutput']);assert sha(path)==row['sha256']
    private_rows.append({'privatePath':str(path),'sha256':row['sha256'],'bytes':path.stat().st_size})
public=[base/folder/name for folder,names in groups.items() for name in names]
public += [base/name for name in ['PRUEBAS_DTLN182_184.md','PRUEBAS_VOZ185_190.md']]
scripts=['dtln_stream182.py','c03-check182.py','c03-prepare183.py','c03-observe184.py','c03-prepare185.py','c03-prepare186.py','c03-observe186.py','c03_tap187.py','c03-prepare187.py','c03-replay188.py','c03-observe189.py','c03-compare190.py']
for stage in [183,185,187]:scripts.extend([f'c03-capture{stage}.py',f'c03-sidecar{stage}.py',f'c03-sidecar{stage}-entry.py'])
public += [root/'scratchpad'/name for name in scripts]
for stage in [184,186,188,189,190]:
    label='replay' if stage==188 else 'compare' if stage==190 else 'observe'
    log=f'c03-{label}{stage}.log'
    path=base/f'astra-{label}{stage}'/log
    path.write_bytes((Path(os.environ['TEMP'])/log).read_bytes());public.append(path)
old=json.loads((base/'TRAMO177_181_PINS.json').read_text(encoding='utf-8'))
assert all(sha(root/r['path'])==r['sha256'] for r in old['public'])
assert all(sha(Path(r['privatePath']))==r['sha256'] for r in old['private'])
pins={'public':[{'path':str(p.relative_to(root)),'sha256':sha(p),'bytes':p.stat().st_size} for p in public],'private':private_rows}
save(base/'TRAMO182_190_PINS.json',pins)
for name in ['CHECKPOINT.md','HANDOFF.md']:
    path=base/name;archive=base/name.replace('.md','_HISTORICO_HASTA184.md')
    assert not archive.exists();archive.write_bytes(path.read_bytes())
handoff='''# Handoff C03 —190 — EN_CURSO —2026-09-07

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, continúa01a074f6-9e0e-7fb3-8282-a6b706198a7e.
Goal íntegro activo, Goal-c03, HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49.
Sin commit/push/main/subagentes. Preservar WIP y evidencia privada/pública.

## Producto y evidencia

Fuente172 vigente: contador de barge consecutivo/una emisión;130pass0skips7,36s
y Fast/Release verdes.164 precarga SciPy antes de JSONL corrigió bloqueo nativo.
UI166 tres horas veraces ~1s,3499,5MiBVRAM; no audio aceptado ni Full actual.
Qwen3.5/Piper/Speex/DTLN siguen candidatos; manifiesto registrado13b971b3… intacto.

182 adaptación DTLN128/512 continua: seis paridades PCM y guard alineado384samples.
183 una interrupción de4;184 confirma primera horaES cortada.185 cero eventos,
snapshot post-barge ausente;186 recupera cada contenido en alguna lectura.
187 cero eventos, captura exacta1249bloques/39,968s y cuatro originales Piper.
188 reproduce PCM128 Y VAD1249/1249 idénticos;128/512 ceroVAD en ese eco.
512 p99 19,38ms/max32,42ms por32ms;128 p99 2,69ms. No coste combinado final.
189 inglés sólo «It is ten» pese a no evento.190 lo mismo en ORIGINAL Piper;
no atribuir esa omisión de ASR a corte/AEC. No demuestra pérdida de Piper.
ASR/ganancia tienen variantes; correlación fuente/loopback0,48–0,70 no certifica
onda íntegra. PRUEBAS_DTLN182_184.md y PRUEBAS_VOZ185_190.md conservan todas lecturas.
DTLN mezcla129/179–181 aún discrepante; AEC3 default/ganancia0,1 ya descartados
por pérdida de palabras. No repetir ganancias/desplazamientos/modelos sin causa.

## Procesos y ficheros

Todos recogidos exit0:18342628/27245,18491987,18596589/13341,18630401,
18752688/89539,18821835,1892240;190 comando terminóexit0 directamente.
Capturas183/185/187: cerooverflows, hilosparados y restauración exacta0/mutedtrue.
TRAMO182_190_PINS.json fija informes/scripts/inputs;177_181 verificado intacto.
No editar ficheros fijados. CHECKPOINT/HANDOFF_HISTORICO_HASTA184 conserva anteriores.
Privado: LOCALAPPDATA/BAXY/C03-sidecar187-private/{generated187.json,npz;
tap187.json,npz;microphone.wav;loopback.wav;tts-state.jsonl}. Índice público187.
Originales22050Hz, cuatro textos del PREREG187; no regenerar para comparación.
Observaciones189: astra-observe189/{PREREG,RESULTS}. Comparación190:
astra-compare190/{PREREG,RESULTS}; se ajustó ganancia/retardo global solamente.
Python: C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.
DTLN128/512 y LiteRT aislados D:/BAXYRuntime/experiments/voice/dtln179 y dtln180.

## Siguiente acción y alcance

Observador independiente ya instalado(Nemotron) sobre originales187 y sus mismas
ventanas189, para separar pronunciación de fallo de Parakeet; no nueva captura.
Usar helper previo181/.66s flush, raw+normalizado sin texto esperado. Conservar
fallos183 y mezcla129; no promoverDTLN por dos negativos físicos sin eventos.
Herencia humana hallada sólo por título/reporte: baseline_real_voice.txt y
REPORTE_NOCHE_STT_PARAKEET_2026_05_23.md en biblioteca/gemma4-agent/documentacion/
03_voz_stt/research. Declaran84RED/180terceros y remiten stt_real_voice_eval.py;
audios NO localizados ni procedencia verificada. No contar como reserva100.

Pendientes íntegros: audio/entrada humana/wake aprobado, ocho rutas finales,
100humanos frescos congelados y100/100(742pool/239revisados;100NOcongelados),
averías/recuperación,UI/runtime/4GB,promoción/regresión/instalación/continuidadC04–C09,
Full entero y publicación fuera main. Tres ingleses ya admitidos por dueño,
no repetir pregunta. C03_ASTRA_AUTORIDAD.md y C03_RESPUESTA_VERAZ.md mandan.
Este turno: progreso por183–190 evidencia nueva; no cierre ni bloqueo externo.
'''
(base/'HANDOFF.md').write_text(handoff,encoding='utf-8')
(base/'CHECKPOINT.md').write_text(handoff.replace('# Handoff C03','# CHECKPOINT C03'),encoding='utf-8')
path=base/'RELEVO_ACTIVO.json';state=json.loads(path.read_text(encoding='utf-8'))
state.update(goalStatus='active',confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='190 completo.187/188 PCM+VAD paridad exacta;ASR inglés incompleto ya sobre original Piper;183 corte y mezcla129 pendientes. Sin fuente nueva.',continuation='Observador independiente de PCM187/loopback189, sin nueva síntesis/captura. Todos los procesos recogidos;C03 íntegro.')
save(path,state)
print(json.dumps({'publicPins':len(public),'privatePins':len(private_rows),'priorPinsVerified':True,'source172Unchanged':True,'goal':'active'}))
