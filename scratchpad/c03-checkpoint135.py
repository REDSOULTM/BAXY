from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import shutil
import psutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-voice134-private'
own_processes = [p.info for p in psutil.process_iter(['pid', 'name']) if p.info['name'] in {'Baxy.exe', 'llama-server.exe', 'piper.exe'}]
assert not own_processes, own_processes
prereg = json.loads((base / 'astra-voice134/PREREG.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((root / p).read_bytes()).hexdigest() == digest for p, digest in prereg['sources'].items())
observation = {'files': [{'privatePath': str(private / name), 'sha256': hashlib.sha256((private / name).read_bytes()).hexdigest()} for name in ['candidate134.json', 'candidate134.npz']]}
with (base / 'astra-voice134/OBSERVATION_INDEX.json').open('x', encoding='utf-8') as f:
    json.dump(observation, f, indent=2)
current = '''## Estado actual y siguiente acción

Fuente119/124 vigente, sin cambios de producto en129–135.119 Piper completo:
311tests/0skips/10,36s y Fast60843exit0.124 eco a cada muestra en250ms/umbral0,55:
109tests/0skips/7,78s, Fast90073exit0. No repetir verdes ni Full durante reparación.
PRUEBAS_AEC129_134.md es el informe vigente; TRAMO129_135_PINS.json fija evidencia.

SpeexDSP1.2.1 oficial compilado MSVC14.44/O2/x64, DLL83456bytes sólo experimental
en D:/BAXYRuntime/experiments/voice/speexdsp129/build.129 denoise-off anulaba además
ganancia de eco;130 adopta defaults del ejemplo upstream. Sin cambiar umbrales,
132/133 sobre direct125, sin off-before de entrenamiento: original interrumpe8/8
alineaciones prefijadas a3,807–3,835s, AEC+guard0/8.131 conserva habla cercana
sintética sola; mezcla omite «aquí BAXY». No aceptación de fidelidad/voz humana.

134 físico experimental (wrappers explícitos, fuente intacta):31558/30068exit0,
speaking5,75s,0barge real; el detector original en sombra habría cancelado1vez sobre
los mismos265bloques. Captura36,41s, volumen0/muted=true restaurado. Procesamiento
completo en vivo media0,470ms/p9910,580ms por32ms.135 ASR61032exit0 recupera frase
completa y UTF-8 en micrófono y loopback (variantes invalid/isn't valid preservadas).
No App/server/Piper/captura/inferencia propios activos. Registro sin promoción.

Siguiente136: integrar AEC antes de VAD/energía/segmentación con un estado por
sesión de captura y cierre en finally. Sustituir NLMS de clips y retirar arrays
reference de _DecodeRequest/pre-roll; transportar indicador AEC aplicado al evento
recognized. Echo guard usa par crudo anterior (latencia512 del preprocesador).
Rutas: voice_aec.py:153–225; voice.py:373,2085–2601; tests/test_mind_voice_runtime.py
llamadas privadas decode y testNLMS; assets.manifest.json/resolvedor. Prototipo
scratchpad/speex_stream134.py y c03-voice134.py, no importarlos desde producto.
Probar limpieza/propiedad de estado nativo, sesiones y guard/AEC antes de físico/UI.

Manifest13b971b3… intacto; Qwen3.5 sólo override; assets119 todavía no promovidos.
App permite wake no calibrado por seam preexistente (MindRuntimeDiscovery.cs:188–208),
no aceptarlo. Reserva742/239, preview0–154; tres ingleses admitidos por «Son turnos
validos» ya registrado, no preguntar ni extender a742. Pendientes íntegros: reserva100,
voz/entrada física y UI final, runtime/regresión, continuidadC04–C09, Full final
entero y publicación fuera de main. Sin subagentes, commits/push ni cambios en main.

'''
checkpoint = (base / 'CHECKPOINT.md').read_text(encoding='utf-8')
begin = checkpoint.index('## Estado actual y siguiente acción')
end = checkpoint.index('## Estado histórico anterior a119')
checkpoint = checkpoint[:begin] + current + checkpoint[end:]
checkpoint = checkpoint.replace('diagnóstico128 — EN_CURSO', 'candidato físico134/observador135 — EN_CURSO', 1)
(base / 'CHECKPOINT.md').write_text(checkpoint, encoding='utf-8')
handoff = '''# Handoff C03 — candidato físico134/observador135 — 2026-09-07

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, Goal-c03,
HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. C03 íntegro activo; CHECKPOINT manda.
WIP/ajeno/evidencia preservados. Sin commit/push/main/subagentes ni bloqueo externo.

Fuente119/124 intacta en129–135.119 proveedor Piper completo311tests/0skips/10,36s,
Fast60843exit0;124retardos de eco109tests/0skips/7,78s, Fast90073exit0. No Full aún.
125 todavía cortaba UTF-8;126–128 probaron límite acústico de correlación.

129 compiló SpeexDSP1.2.1 oficial con MSVC14.44/O2/x64; DLL83456bytes en
D:/BAXYRuntime/experiments/voice/speexdsp129/build/speexdsp.dll. No instalado ni
integrado.129 denoise-off también anulaba supresión residual;130 defaults oficiales.
132/133 sin entrenar off-before: sobre direct125, raw+guard interrumpe8/8 fases
prefijadas, AEC+guard0/8. Voz cercana sintética preservada sola, mezcla pierde
«aquí BAXY»: no fidelidad completa. PRUEBAS_AEC129_134.md/TRAMO129_135_PINS.json.
134 prototipo físico:31558/30068exit0,5,75s/0barge; detector original en sombra
cancelaría1vez sobre mismos265bloques. Volumen0/muted=true restaurado.13561032exit0
recupera frase/UTF-8 en micrófono y loopback. En vivo media0,470ms/p9910,580ms por32ms.
No UI/producto final ni doble voz humana acreditados; no App/server/Piper/captura/ASR activos.

Siguiente136: integrar un AEC por sesión en captura antes de VAD/energía/streaming;
destruir estado nativo en finally del mismo hilo. Sustituir EchoCanceller NLMS
offline y retirar sus referencias transportadas por _DecodeRequest/pre-roll.
El evento recognized debe recibir indicador AEC aplicado, sin segundo procesamiento.
Guard usa micrófono/referencia crudos del bloque previo: latencia512 del preproceso.
voice_aec.py:153–225; voice.py:373,2085–2601; tests/test_mind_voice_runtime.py privados
decode/testNLMS; asset/resolvedor deben identificar DLL. Prototipo scratchpad/
speex_stream134.py y c03-voice134.py son evidencia, no módulos para importar en src.
Pruebas de propiedad/limpieza/sesiones y guard antes de nueva medición física/UI.

Manifest13b971b3… intacto; Qwen3.5 override. App permite wake no calibrado por seam
preexistente MindRuntimeDiscovery.cs:188–208; no aceptación. Reserva742/239 preview
0–154; faltan155–238 y congelar100 antes de inferir. Tres ingleses «Son turnos validos»
admitidos; no preguntar ni extender a742. Cierre sigue exigiendo ocho rutas/reserva100,
voz/entrada/UI física, runtime+regresión, continuidadC04–C09, Full íntegro final y
publicación propia fuera de main. Python runtime LOCALAPPDATA/BAXYRuntime/python/
mind-runtime-v1/Scripts/python.exe; calidad con resolvedor normal; UI py main.py/CUA.
'''
(base / 'HANDOFF.md').write_text(handoff, encoding='utf-8')
relay = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=dt.datetime.now(dt.timezone.utc).isoformat(),
             checkpoint='Fuente119/124 intacta; candidato AEC134 físico sin corte, sombra original1corte;135contenido completo; C03 EN_CURSO',
             continuation='Sin procesos propios. Integrar AEC en captura sustituyendo NLMS de clips; estado por sesión y pruebas dueñas. CHECKPOINT/PRUEBAS_AEC129_134 mandan. No Full durante reparación.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(relay, indent=2, ensure_ascii=False), encoding='utf-8')
files = ['PRUEBAS_AEC129_134.md', 'astra-analysis135/PREREG.json', 'astra-analysis135/RESULT_INDEX.json']
for number in [129, 130, 132]:
    files.extend([f'astra-speex{number}/PREREG.json', f'astra-speex{number}/RESULTS.json'])
for number in [131, 133]:
    files.extend([f'astra-speex{number}/RESULTS.json', f'astra-speex{number}/LIMITS.json'])
files.extend([f'astra-voice134/{name}' for name in ['PREREG.json','RESULTS.json','EVENTS.jsonl','AUDIO_RESULT.json','OBSERVATION_INDEX.json']])
pins = {str((base / p).relative_to(root)).replace('\\','/'): hashlib.sha256((base / p).read_bytes()).hexdigest() for p in files}
for name in ['c03-speex129.py','c03-speex130.py','c03-check-speex131.py','c03-speex132.py','c03-check-speex133.py','c03-voice134.py','speex_stream134.py','c03-build-speex129.cmd','c03-speex129.def','c03-analyze-voice135.py']:
    path = root / 'scratchpad' / name
    pins[str(path.relative_to(root)).replace('\\','/')] = hashlib.sha256(path.read_bytes()).hexdigest()
download = Path('D:/BAXYRuntime/experiments/voice/speexdsp129/DOWNLOAD.json')
shutil.copyfile(download, base / 'astra-speex129/DOWNLOAD.json')
shutil.copyfile(Path(os.environ['TEMP']) / 'c03-speex129-build.log', base / 'astra-speex129/BUILD.log')
for name in ['DOWNLOAD.json','BUILD.log']:
    path = base / 'astra-speex129' / name
    pins[str(path.relative_to(root)).replace('\\','/')] = hashlib.sha256(path.read_bytes()).hexdigest()
with (base / 'TRAMO129_135_PINS.json').open('x', encoding='utf-8') as f:
    json.dump({'createdUtc': dt.datetime.now(dt.timezone.utc).isoformat(), 'files': pins}, f, indent=2)
assert all(hashlib.sha256((root / p).read_bytes()).hexdigest() == digest for p, digest in pins.items())
print(json.dumps({'verifiedPins':len(pins), 'productSourceUnchangedSince134':True, 'productProcesses':own_processes}))
