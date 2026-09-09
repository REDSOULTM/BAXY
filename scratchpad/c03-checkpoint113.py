from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
for name in ('CHECKPOINT', 'HANDOFF'):
    with (base / f'{name}_HISTORICO_HASTA113.md').open('x', encoding='utf-8', newline='\n') as f:
        f.write((base / f'{name}.md').read_text(encoding='utf-8-sig'))

current = '''## Estado actual y siguiente acción

Fuente112 adoptada sobre108: Piper recibe PAD después de cada fonema conocido.
Native111 recupera saludo y dos relojes españoles; inglés sigue alterado.
85 pruebas de voz pass/0skips,7,76s; Fast33691 exit0,Release3,37s,0avisos/errores.
ASTRA-TRAMO-112.md y PRUEBAS_AUDIO110_NATIVE111.md. No repetir verdes ni Full.

Native11358330 exit0: misma voz es_MX-claude-high/PAD, sólo eSpeak es-419/en-us.
en-us recupera It is seven fourteen.; UTF-8 pasa a you'll be the fake y read
a heal. No acredita inglés fiel; no adoptar sólo cambio de fonemizador.
RESULTS/PREREG en astra-native-tts113. PCM nativo/ASR, no audio físico.
Siguiente: medir una voz Piper entrenada en inglés sobre estos mismos tres
textos consumidos; herencia Carter MODEL_TTS_TOURNAMENT_REPORT (2026-05-02)
advierte modelos por idioma, pero sus latencias eran scaffold, no aceptación.
No modelo ni selector de idioma adoptados; registro intacto.

Audio11076726/87021 exit0: UI muestra tres relojes fieles ES/EN/mezcla, pero
ASR de mic/loopback no recupera contenido. Última ventana acortada a4,56s.
GPU3502,296875MiB/RAM6015,91796875MiB con wake1,200,45s; primer1,032s excluido.
Grabaciones privadas en LOCALAPPDATA/BAXY/C03-audio110-private. Volumen
restaurado exactamente0/muted=true. Ningún App/server/captura/inferencia activo.
No aceptación acústica ni entrada hablada. Voz45 tenía83tests, no tramo83.

Fuente108/UI109 conservada: Error y Response error ante avería real; recuperación
Son las07:02. en mismo proceso.169tests/Fast verdes; PRUEBAS_UI109.md y
TRAMO108_109_PINS.json. UI107 confirma/cancela/cierra fielmente fixture real.
UI104 progreso visible y ocho finales fieles;106 averías/restauración aparte.
No repetir estos paneles sin dato nuevo. Sello UI108 conserva38archivos,
99FF9838C07CE32F25F329AACF830F62D8DD70C5931E26C2EC483B710B2CA657.

Reserva privada742/239no refutados, preview105 vistos0–154; falta155–238,
seleccionar100 literales humanos/contextuales y congelar antes de inferencia.
Tres textos ingleses admitidos por dueño en ADMISIBILIDAD_DUENO_2026-09-06.md;
no preguntar ni extender confirmación a742. C03 EN_CURSO completo: voz/audio,
reserva100, promoción/regresión del runtime, continuidadC04–C09, Full final verde
y publicación validada fuera de main pendientes. Sin subagentes ni commit/push.

'''
checkpoint = base / 'CHECKPOINT.md'
text = checkpoint.read_text(encoding='utf-8-sig')
text = '# C03 — CHECKPOINT — fuente112/native113 — EN_CURSO\n' + text[text.index('\n'):]
start, end = text.index('## Estado actual'), text.index('## Decisiones y pruebas')
text = text[:start] + current + text[end:]
tail = text.find('\nAudio110 ACTIVO:')
if tail >= 0:
    text = text[:tail].rstrip() + '\n'
checkpoint.write_text(text, encoding='utf-8', newline='\n')
(base / 'HANDOFF.md').write_text('''# Handoff C03 — fuente112/native113 — 2026-09-07

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, Goal-c03,
HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Objetivo C03 completo vigente;
CHECKPOINT manda. Preservar WIP/ajeno/evidencia y main.

''' + current + '''Python runtime para voz: LOCALAPPDATA/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.
Calidad usa resolvedor predeterminado; GUI únicamente py main.py.
Qwen3.5-4B-Q4_K_M sigue override, registro Qwen3-4B intacto. Sin procesos propios.
''', encoding='utf-8', newline='\n')
relay_path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(relay_path.read_text(encoding='utf-8-sig'))
relay.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    checkpoint='Fuente112 PAD corregido,85tests/Fast verdes; native113 inglés insuficiente; C03 EN_CURSO',
    continuation='Sin procesos propios. Medir voz inglesa nativa en mismos3textos; no adoptar sólo en-us. CHECKPOINT manda; no Full durante reparación.')
relay_path.write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
report = base / 'ASTRA-TRAMO-112.md'
text = report.read_text(encoding='utf-8')
start, end = text.index('fielmente con es-419.'), text.index('\nLa verificación acústica')
text = text[:start] + '''fielmente con es-419. Native11358330 exit0: tres respuestas inglesas consumidas
del producto, misma voz ONNX, sólo eSpeak es-419/en-us con PAD corregido.
en-us recupera el reloj, pero altera UTF-8 (you'll be the fake) y read (heal).
No resuelve3/3; no adoptar sólo fonemizador ni llamar fiel a una transcripción
que cambia hechos. No semilla ONNX fija: comparación de contenido, no igualdad
de ondas. RESULTS/PREREG en astra-native-tts113. Siguiente hipótesis: voz
entrenada en inglés, mismo motor y textos; no selector/modelo adoptados.
''' + text[end:]
report.write_text(text, encoding='utf-8', newline='\n')
def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
paths = ['src/baxy_mind/voice_output.py', 'tests/test_neural_speech_output.py']
for rel in ('ASTRA-TRAMO-112.md', 'PRUEBAS_AUDIO110_NATIVE111.md',
            'astra-audio110/PREREG.json', 'astra-audio110/RESOURCES.json',
            'astra-audio110/AUDIO_RESULT.json', 'astra-audio110/TRANSCRIPTION_INDEX.json',
            'astra-native-tts111/PREREG.json', 'astra-native-tts111/RESULTS.json',
            'astra-native-tts113/PREREG.json', 'astra-native-tts113/RESULTS.json'):
    paths.append('artifacts/comprobaciones/C03/' + rel)
pins = {p: sha(root / p) for p in paths}
with (base / 'TRAMO110_113_PINS.json').open('x', encoding='utf-8') as f:
    json.dump({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': pins}, f, indent=2)
print('Checkpoint113 saved; source/evidence pinned; no product/runtime mutation.')
