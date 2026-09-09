from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import shutil
import psutil

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
live = [p.info for p in psutil.process_iter(['pid','name']) if p.info['name'] in {'Baxy.exe','llama-server.exe','piper.exe'}]
assert not live,live
current = '''## Estado actual y siguiente acción

Fuente136 integra SpeexAEC antes de VAD/segmentación/streaming con un estado por
sesión, cierre en hilo dueño, guard alineado a latencia512, y aec_applied explícito.
Retira NLMS de clips, referencias transportadas a ASR y seam de cola diagnóstica.
Nuevo src/baxy_mind/speex_aec.py; asset echo_canceller staged en D:/BAXYRuntime/
assets/aec/speexdsp-1.2.1/speexdsp.dll, SHA bb683ab3c50f66f777f0d2eb570b57c0ef5c71cb7e45535f9625a3f2ab56d9f1.
Manifest de runtime intacto.130tests/0skips/10,64s; Fast39832exit0/Release3,14s.
Después de corregir caller run_voice_system_gate y docs: Fast29493exit0/Release3,01s,
0avisos/errores. Componente AEC de esa compuerta15,99dB con umbral6dB intacto;
no compuerta física completa.137 reproduce265pares134 con PCM bitidéntico.

136 sigue candidato:138 sin wrappers falla1,578s/2barge;139 con observación pasa
5,578s/0barge. Ambos terminaron y restauraron0/muted=true. No elegir el pase.
140 confirma por hashes referencias consumidas discontinuas: durante audio activo
2repeticiones y1salto de3bloques (omite2); latest512 depende del ritmo del lector.
ASTRA-TRAMO-136.md y PRUEBAS_REFERENCIA138_142.md; TRAMO136_142_PINS.json.

141/142 sólo miden relojes, sin guardar PCM/reproducir/cambiar volumen. MME Realtek:
109callbacks con ADC/currentTime cero. WASAPI mismo mic por default_input_device
(12 aquí), shared/auto_convert a16k:109/109ADC válidos; loopback112/112, cero flags.
Relojes nativos comparten base con perf_counter; jitter de varios ms. No asumir
timestamps perfectos ni sincronizar con el momento en que se planifica el hilo.

Siguiente143: reemplazar lectura MME/latest por captura WASAPI con timestamps y
referencia continua por índice de muestra. Anclar orígenes una vez y avanzar512
por frame; esperar datos de forma acotada/cancelable, error honesto en overflow,
sin saltar/repetir ni tocar umbrales. Callback con trabajo acotado; warmup scipy
fuera de callback y ring circular si se cambia almacenamiento. Mantener único DSP.
use_pcm_source es diagnóstico Goal09 sin reloj de mic: no inventarle ADC ni AEC
con el escritorio. Rutas voice.py:1579,2085–2600; voice_aec.py:45–140; prototipo de
reloj scratchpad/c03-audio-clocks142.py. Probar continuidad/ráfagas/cancelación y
medir físico sin wrappers antes de UI. No nueva modificación de referencia aún.

Sin procesos propios App/server/Piper/captura/inferencia; todas sesiones139/Fast
terminales exit0. No Full en reparación. Fuente/fixtures/snapshots preservados,
sin commits/push/main/subagentes. C03 íntegro EN_CURSO, sin bloqueo externo.
Qwen3.5 sólo override; assetsPiper/John/AEC sin promoción. App wake no calibrado
por seam preexistente (MindRuntimeDiscovery.cs:188–208) no aceptado. Reserva742/239,
preview0–154; tres ingleses admitidos «Son turnos validos», no preguntar ni extender.
Siguen ocho rutas/reserva100 congelada, entrada+salida/UI física, runtime/regresión,
continuidadC04–C09, Full íntegro final y publicación propia fuera de main.

'''
checkpoint = (base/'CHECKPOINT.md').read_text(encoding='utf-8')
first = checkpoint.index('## Estado actual y siguiente acción')
last = checkpoint.index('## Evidencia hasta135')
checkpoint = checkpoint[:first]+current+checkpoint[last:]
checkpoint = checkpoint.replace('diagnóstico de referencia139', 'referencia/relojes142',1)
(base/'CHECKPOINT.md').write_text(checkpoint,encoding='utf-8')
handoff = '''# Handoff C03 — fuente136/referencia142 — 2026-09-07

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, Goal-c03,
HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Goal íntegro activo; CHECKPOINT manda.
WIP/ajeno/evidencia preservados. Sin commit/push/main/subagentes ni bloqueo externo.

136 integra Speex por sesión antes de VAD/segmentación/streaming; guard usa par
crudo del bloque anterior por latencia512. Retira NLMS de clips y transporte
reference a ASR; aec_applied explícito, cierre en dueño, estado/hash honestos.
Nuevo speex_aec.py, tests/test_speex_aec.py; 16calls privadas decode actualizadas,
3tests de captura/limpieza.130pass/0skips/10,64s; Fast39832exit0. Caller de compuerta
run_voice_system_gate adaptado:componente15,99dB con umbral6 intacto; no gate físico.
Fast final29493exit0/Release3,01s/0avisos/errores. No Full durante reparación.
DLL staged D:/BAXYRuntime/assets/aec/speexdsp-1.2.1/speexdsp.dll, SHA bb683ab3…,
licencia/receta al lado; manifest runtime no promovido.137265pares134 bitidénticos.

138 fuente integrada falla físicamente1,578s/2barge.139 observador pasa5,578s/0barge;
no aceptar por elegir139.140 hashes prueban latest512 repite/salta referencia incluso
con señal activa.141 MME Realtek ADC/currentTime0 en109callbacks;142 WASAPI mismo
micro default_input_device12/shared auto_convert16k da109/109ADC válidos; loop112/112,
cero flags. Relojes comparten base perf_counter, con jitter.141/142 no guardan PCM,
reproducen ni cambian volumen. PRUEBAS_REFERENCIA138_142.md/ASTRA-TRAMO-136.md,
TRAMO136_142_PINS.json y snapshots. No App/server/Piper/captura/inferencia activos.
138/139 restauraron0/muted=true; sesiones y último Fast recogidos exit0.

Siguiente143: captura WASAPI timestampada + referencia por índice continuo,
anclada una vez, avance512; no latest para alimentar filtro. Esperas acotadas/
cancelables y fallos honestos de overflow. Warmup scipy fuera del callback; trabajo
acotado/ring sin copia completa. Mantener único DSP136; no bajar umbrales.
voice.py:1579,2085–2600; voice_aec.py:45–140; scratchpad/c03-audio-clocks142.py.
use_pcm_source sólo diagnóstico Goal09 sin reloj: no AEC con referencia desktop
inventando tiempos. Probar continuidad/ráfagas/cierre antes de físico sin wrappers/UI.

Qwen3.5 sólo override, Piper/John/AEC sin promoción. App permite wake no calibrado
por seam MindRuntimeDiscovery.cs:188–208; no aceptado. Reserva742/239, preview0–154,
faltan155–238 y congelar100. Tres ingleses «Son turnos validos» admitidos; no repetir
pregunta ni extender. Cierre íntegro: ocho rutas/reserva100, voz humana+UI/audio físico,
runtime/regresión, continuidadC04–C09, Full entero final y publicación fuera de main.
Python runtime LOCALAPPDATA/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe;
Fast resolvedor normal, interfaz sólo py main.py/Computer Use.
'''
(base/'HANDOFF.md').write_text(handoff,encoding='utf-8')
relay = json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=dt.datetime.now(dt.timezone.utc).isoformat(),
    checkpoint='Fuente136130tests/Fast verdes pero138 físico falla;140continuidad rota y142WASAPI con ADC válido; C03 EN_CURSO',
    continuation='Sin procesos propios.143 captura WASAPI timestampada y referencia por índice continuo; no umbrales ni más AEC. CHECKPOINT/PRUEBAS_REFERENCIA138_142 mandan. No Full en reparación.')
(base/'RELEVO_ACTIVO.json').write_text(json.dumps(relay,indent=2,ensure_ascii=False),encoding='utf-8')
snapshot = base/'astra-source136-snapshot'
snapshot.mkdir(exist_ok=False)
source_files = ['src/baxy_mind/speex_aec.py','src/baxy_mind/voice.py','src/baxy_mind/voice_aec.py',
    'tests/test_speex_aec.py','tests/test_mind_voice_runtime.py','scripts/run_voice_system_gate.py',
    'assets.manifest.json','docs/AI_CONTEXT_MAP.md']
pins = {}
for name in source_files:
    target = snapshot/name.replace('/','__')
    shutil.copyfile(root/name,target)
    pins[str(target.relative_to(root)).replace('\\','/')] = hashlib.sha256(target.read_bytes()).hexdigest()
for name in ['c03-source136-tests-final.log','c03-source136-capture-tests.log','c03-source136-fast-final.log','c03-source136-fast-maintenance.log']:
    target = snapshot/name
    shutil.copyfile(Path(os.environ['TEMP'])/name,target)
    pins[str(target.relative_to(root)).replace('\\','/')] = hashlib.sha256(target.read_bytes()).hexdigest()
files = ['ASTRA-TRAMO-136.md','PRUEBAS_REFERENCIA138_142.md','astra-native137/PREREG.json','astra-native137/RESULTS.json']
for number in [138,139]:
    files += [f'astra-voice{number}/{name}' for name in ['PREREG.json','RESULTS.json','EVENTS.jsonl','AUDIO_RESULT.json']]
files += ['astra-voice139/TIMING_INDEX.json']
for number in [141,142]:
    files += [f'astra-clocks{number}/{name}' for name in ['RESULTS.json','SUMMARY.json']]
for name in files:
    path = base/name
    pins[str(path.relative_to(root)).replace('\\','/')] = hashlib.sha256(path.read_bytes()).hexdigest()
for name in ['c03-native137.py','c03-voice138.py','c03-voice139.py','c03-analyze-timing140.py','c03-audio-clocks141.py','c03-audio-clocks142.py']:
    path = root/'scratchpad'/name
    pins[str(path.relative_to(root)).replace('\\','/')] = hashlib.sha256(path.read_bytes()).hexdigest()
with (base/'TRAMO136_142_PINS.json').open('x',encoding='utf-8') as f:
    json.dump({'createdUtc':dt.datetime.now(dt.timezone.utc).isoformat(),'files':pins},f,indent=2)
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest() == digest for name,digest in pins.items())
print(json.dumps({'pinsVerified':len(pins),'productProcesses':live,'stateWritten':True}))
