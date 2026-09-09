from pathlib import Path
import datetime
import hashlib
import json
import os
import psutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
assert sha(manifest) == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
source = root / 'src/baxy_mind/voice_output.py'
prior = json.loads((base / 'astra-native-tts118/PREREG.json').read_text(encoding='utf-8')) if (base / 'astra-native-tts118/PREREG.json').exists() else json.loads((base / 'astra-reference-tts118/PREREG.json').read_text(encoding='utf-8'))
assert sha(source) == prior['sourceSha256']
assert not any(p.info['name'] in {'Baxy.exe', 'llama-server.exe', 'piper.exe'} for p in psutil.process_iter(['name']))
for name in ('CHECKPOINT', 'HANDOFF'):
    with (base / f'{name}_ANTES_DE118.md').open('x', encoding='utf-8', newline='\n') as f:
        f.write((base / f'{name}.md').read_text(encoding='utf-8-sig'))
current = '''## Estado actual y siguiente acción

Fuente112/UI108 sigue adoptada;114–118 son mediciones nativas sin edición de
producto. PRUEBAS_TTS114_118.md contiene decisiones, literales, hashes y límites.
Nuevo defecto localizado: el adaptador manual eSpeak pierde terminadores,
límites de oración, NFD y flags que sí conserva el frontend oficial Piper.
Native117 aísla punto final real: mismos3textos/voz inglesa/engine112; contenido
3/3 recuperado por Parakeet. No adoptar un parche de añadir puntos a todo.
Reference1187916exit0: Piper oficial Windows2023.11.14-2, misma voz española y
John inglesa, seis controles ES/EN con contenido recuperado. CLI por turno
0,844–1,218s, carga del modelo~0,6s. No aceptación de audio físico ni UI.
Contraste de backend/frontend completo, no atribuir todo118 sólo a puntuación.
C++ incluye PAD también trasBOS; referencia Python112 no: contrato distinto.

John medium114:63.531.379bytes, SHA789c6c875726e627ddee93d51d8727859abe9c091c3d141591f4b83c2072e988,
configen/familiaen_US, dataset LibriVox dominio público según ficha primaria.
D:/BAXYRuntime/experiments/voice/c03-john114. No otro modelo descargado.
Piper referencia en D:/BAXYRuntime/experiments/voice/piper-reference118/piper.
ZIPSHAf3c58906402b24f3a96d92145f58acba6d86c9b5db896d207f78dc80811efcea.
DLL eSpeak antigua no expone terminador; wheel piper-phonemize no ofreceWindows.
115/116: observador Nemotron existente, mismos WAVs, sin resíntesis.115 sin
flush truncaba;116 añade0,66s de silencio del ejemplo Sherpa y recupera UTF eight.
Eso limita la atribución al TTS de errores de Parakeet; no es prueba humana.

Siguiente implementación: sustituir el frontend manual por Piper completo
probado y retirar el motor sustituido; conservar propietario único de cola,
playback/cancelación. CLI por invocación es la referencia sencilla medida;
debe cancelar su hijo durante síntesis y comprobar coste integrado. Seleccionar
voz con evidencia del texto hablado, reutilizando request_reading, sin obedecer
instrucciones citadas en respuestas. No duplicar clasificador ni protocolo.
Revisar voice_output.py:342–487,624–714; callers measure_goal09_voice.py:186,
test_goal09_voice_engines.py:27/116 y ttsSha256 en voice.py:1685 para no informar
hash español cuando se usa voz inglesa. Asset/registro/modelos deben quedar
reproducibles con ambos idiomas antes de promoción. No cambio adoptado aún.

Fuente112 PAD:85pruebas voz pass/0skips,7,76s; Fast33691exit0,Release3,37s,
0avisos/errores. TRAMO110_113_PINS.json. No repetir verdes ni Full durante reparación.
Audio110: UI tres relojes fieles pero ASR físico no recuperado, última ventana
acortada. GPU3502,296875MiB/RAM6015,91796875MiB con wake1; arranque1,032s excluido.
Capturas privadas LOCALAPPDATA/BAXY/C03-audio110-private, volumen restaurado0/muted=true.
Ningún App/server/Piper/captura/inferencia activo; registro intacto y sin promoción.

UI108/109 error visible/restauración,169tests/Fast verdes; UI107 confirmación/
cancelación/cierre; UI104 progreso y ocho finales. No repetir paneles sin dato nuevo.
Reserva742/239, preview0–154; faltan155–238, selección/congelación100 humanos
antes de inferencia. Tres ingleses confirmados por dueño ya registrados; no
preguntar ni extendera742. Voz/audio físico+entrada, reserva100, promoción/regresión,
continuidadC04–C09, Full final entero y publicación validada fuera de main siguen
pendientes. C03 EN_CURSO íntegro; sin subagentes, commit/push ni cambios en main.

'''
checkpoint = base / 'CHECKPOINT.md'
text = checkpoint.read_text(encoding='utf-8-sig')
text = '# C03 — CHECKPOINT — fuente112/reference118 — EN_CURSO\n' + text[text.index('\n'):]
start, end = text.index('## Estado actual'), text.index('## Decisiones y pruebas')
text = text[:start] + current + text[end:]
checkpoint.write_text(text, encoding='utf-8', newline='\n')
(base / 'HANDOFF.md').write_text('''# Handoff C03 — fuente112/reference118 — 2026-09-07

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, Goal-c03,
HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Goal activo completo;
CHECKPOINT manda. WIP/ajeno/evidencia preservados, main excluida.

''' + current + '''Python runtime para voz: LOCALAPPDATA/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.
Calidad usa resolvedor predeterminado; GUI sólo py main.py/Computer Use.
Qwen3.5 sigue override, registro Qwen3-4B intacto; no procesos propios.
''', encoding='utf-8', newline='\n')
relay_path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(relay_path.read_text(encoding='utf-8-sig'))
relay.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    checkpoint='Fuente112 vigente;117 punto aislado3/3, Piper referencia118 seis contenidos ES/EN; C03 EN_CURSO',
    continuation='Sin procesos propios. Sustituir frontend manual por Piper completo medido, selección de idioma y assets reproducibles; validar dueño/coste/cancelación. CHECKPOINT manda, no Full durante reparación.')
relay_path.write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
paths = ['PRUEBAS_TTS114_118.md', 'astra-native-tts114/DOWNLOAD.json',
         'astra-native-tts114/PREREG_ABORTED_BEFORE_SYNTHESIS.json',
         'astra-native-tts114/SETUP_ABORT.log', 'astra-native-tts114/CONSOLE_ABORT.log']
for folder in ('astra-native-tts114', 'astra-observe-tts115', 'astra-observe-tts116',
               'astra-native-tts117', 'astra-reference-tts118'):
    paths += [folder + '/PREREG.json', folder + '/RESULTS.json']
files = {'artifacts/comprobaciones/C03/' + p: sha(base / p) for p in paths}
files['src/baxy_mind/voice_output.py'] = sha(source)
for name in ('c03-prepare-tts114.py', 'c03-native-tts114.py', 'c03-observe-tts115.py',
             'c03-native-tts117.py', 'c03-reference-tts118.py'):
    files['scratchpad/' + name] = sha(root / 'scratchpad' / name)
with (base / 'TRAMO114_118_PINS.json').open('x', encoding='utf-8') as f:
    json.dump({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': files,
               'note': 'WAV hashes are in the pinned RESULTS; downloaded assets in pinned DOWNLOAD/PREREG.'}, f, indent=2)
print(json.dumps({'state': 'EN_CURSO', 'sourceSha256': sha(source), 'runtimeUnchanged': True,
                  'ownedInferenceProcesses': 0, 'pinnedFiles': len(files)}))
