"""Persist the bounded current state and pin named evidence, not the whole tree."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import psutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
live = [p.info for p in psutil.process_iter(['pid', 'name']) if p.info['name'] in {'Baxy.exe', 'llama-server.exe', 'piper.exe'}]
assert not live, live
handoff = '''# Handoff C03 — fuente119/124, diagnóstico128 — 2026-09-07

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, Goal-c03,
HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Objetivo C03 íntegro activo;
CHECKPOINT manda. WIP/ajeno/evidencia preservados; sin commit/push/main/subagentes.

119 integra Piper completo y retira frontend manual, selección ES/EN/hash por texto,
cola/playback dueño y cancelación de hijo.311tests/0skips/10,36s; Fast60843exit0.
120 seis contenidos fieles por cola+sink, cancelación real94ms/hijo recogido.
124 busca cada retardo de eco en250ms, umbral0,55 intacto.109tests/0skips/7,78s;
Fast90073exit0. Sin Full durante reparación. PRUEBAS_VOZ119_125.md.

121 UI fiel pero acústica fallida; GPU3513,41796875MiB.123 escucha cancela a1,469s;
125 mejora a3,938s pero aún corta frente aoff5,562/5,359s.126 ASR de capturas
privadas: off/off frase completa, direct125 pierde UTF-8 en micrófono y loopback.
127 observador de entradas/salidas exactas:5,562s/0barge. No aceptar por un pase
variable: wrappers de diagnóstico, una fase distinta, sin App/LLM.128 encuentra
10frames con energía/VAD y score insuficiente;9 siguen bajo0,55 buscando toda la
referencia externa. Ampliar retardo no basta. PRUEBAS_ECO126_128.md, índices privados
con hashes, TRAMO119_128_PINS.json. Fuente119/124 no modificada en126–128.

Siguiente: evaluar AEC adaptativo existente para Windows sobre capturas privadas127
y controles de voz cercana/silencio/doble voz. voice_aec.py:153–225 NLMS actual sólo
procesa clips, llamado voice.py:2600 después del barge-in2342–2367. Fuentes Speex/
WebRTC en informe; nada nuevo descargado ni adoptado. No bajar umbral ni sumar
motores. No más reproducción hasta probar hipótesis offline. Contador no resetea
en no-voz; observado, no demostrado como causa125 ni corregido.

Sin App/server/Piper/captura/inferencia propios;127 terminó73458/49180exit0 y
restauró0/muted=true. Manifest intacto13b971b3…, Qwen3.5 sólo override. John/Piper
staged con hashes en informe119, registro no promovido. App habilita wake no
calibrado (MindRuntimeDiscovery.cs:188–208); seam preexistente, no aceptación.
Reserva742/239, preview0–154; faltan155–238 y congelar100 antes de inferencia.
Tres ingleses admitidos por «Son turnos validos»: ya registrado, no preguntar ni
extender a742. Pendientes completos: ocho rutas/reserva100, voz+entrada física,
runtime/regresión, continuidadC04–C09, Full final entero y publicación fuera de main.
Python runtime LOCALAPPDATA/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe;
calidad con resolvedor predeterminado; GUI sólo py main.py/Computer Use.
'''
(base / 'HANDOFF.md').write_text(handoff, encoding='utf-8')
relay = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
             checkpoint='Fuente119/124;126 contenido físico truncado en direct,127/128 límite de similitud acústica; C03 EN_CURSO',
             continuation='Sin procesos propios. Evaluar AEC adaptativo existente sobre capturas privadas y controles antes de otra reproducción. CHECKPOINT/PRUEBAS_ECO126_128 mandan. No Full durante reparación.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(relay, indent=2, ensure_ascii=False), encoding='utf-8')
snapshot = base / 'astra-source124-snapshot'
snapshot.mkdir(exist_ok=False)
files = [
    'src/baxy_mind/voice.py', 'src/baxy_mind/voice_output.py', 'src/baxy_mind/piper_tts.py',
    'src/baxy_mind/voice_aec.py', 'src/baxy_mind/request_reading.py', 'assets.manifest.json',
    'tests/test_piper_tts.py', 'tests/test_neural_speech_output.py', 'tests/test_mind_voice_runtime.py',
]
pins = {}
for relative in files:
    source = root / relative
    target = snapshot / relative.replace('/', '__')
    shutil.copyfile(source, target)
    pins[str(target.relative_to(root)).replace('\\', '/')] = hashlib.sha256(target.read_bytes()).hexdigest()
reports = ['ASTRA-TRAMO-119.md', 'PRUEBAS_VOZ119_125.md', 'PRUEBAS_ECO126_128.md',
           'ADMISIBILIDAD_DUENO_2026-09-06.md', 'astra-analysis126/PREREG.json', 'astra-analysis126/RESULT_INDEX.json']
for number in [123, 125, 127]:
    reports += [f'astra-voice{number}/{name}' for name in ['PREREG.json', 'RESULTS.json', 'EVENTS.jsonl', 'AUDIO_RESULT.json']]
reports += ['astra-voice127/OBSERVATION_INDEX.json', 'astra-native-voice120/PREREG.json', 'astra-native-voice120/RESULTS.json']
for relative in reports:
    source = base / relative
    pins[str(source.relative_to(root)).replace('\\', '/')] = hashlib.sha256(source.read_bytes()).hexdigest()
for name in ['c03-source119-tests-final.log', 'c03-source119-fast-final.log', 'c03-echo124-tests.log', 'c03-echo124-fast.log']:
    source = Path(os.environ['TEMP']) / name
    target = snapshot / name
    shutil.copyfile(source, target)
    pins[str(target.relative_to(root)).replace('\\', '/')] = hashlib.sha256(target.read_bytes()).hexdigest()
with (base / 'TRAMO119_128_PINS.json').open('x', encoding='utf-8') as stream:
    json.dump({'createdUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': pins}, stream, indent=2)
assert all(hashlib.sha256((root / p).read_bytes()).hexdigest() == digest for p, digest in pins.items())
print(json.dumps({'pinsVerified': len(pins), 'productProcesses': live, 'handoffUpdated': True}))
