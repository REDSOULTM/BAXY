from pathlib import Path
import json
import hashlib
import os
from datetime import datetime, timezone

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-sidecar168'
out.mkdir(exist_ok=False)
compositions=[json.loads(line) for line in (base/'astra-audio166/compose-audit.jsonl').read_text(encoding='utf-8').splitlines()]
texts=[row['draft'] for row in compositions if row.get('published')]
assert len(texts)==4
prereg={'method':'Full original JSONL sidecar164, actual catalog169 and same observed App environment/Qwen override. Four consumed published166 outputs. Greeting then wake startup as App; wait10s after start and after each remaining speak. Physical capture and exact volume restore. Only diagnostic addition logs output last_error/time on each speaking state (not per frame; calls original unchanged). No playback/DSP/VAD/OutputStream wrappers. Determine barge_in versus TTS failure; not acceptance.', 'texts':texts,'sourceFiles':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['src/baxy_mind/__main__.py','src/baxy_mind/voice_aec.py','src/baxy_mind/voice.py','src/baxy_mind/voice_output.py','src/baxy_mind/piper_tts.py']}}
(out/'PREREG.json').write_text(json.dumps(prereg,indent=2,ensure_ascii=False),encoding='utf-8')
capture=(root/'scratchpad/c03-capture-audio166.py').read_text(encoding='utf-8').replace('astra-audio166','astra-sidecar168').replace('C03-audio166-private','C03-sidecar168-private')
(root/'scratchpad/c03-capture168.py').write_text(capture,encoding='utf-8')
driver=(root/'scratchpad/c03-sidecar165.py').read_text(encoding='utf-8').replace('165','168')
driver=driver.replace('out.mkdir(exist_ok=False)', "assert (out/'AUDIO_READY.json').exists()")
driver=driver.replace('private.mkdir(exist_ok=False)', 'assert private.is_dir()')
driver=driver.replace("out/'PREREG.json'", "out/'RUNTIME_CONFIG.json'")
driver=driver.replace("rows=[]", "texts=json.loads((out/'PREREG.json').read_text(encoding='utf-8'))['texts']\nrows=[]")
driver=driver.replace("'¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?'", 'texts[0]')
driver=driver.replace("    for message,timeout in sequence:", "    sequence.extend(({'type':'voice.speak','id':f'speak{index}','text':value},10) for index,value in enumerate(texts[1:],1))\n    for message,timeout in sequence:")
driver=driver.replace("except Exception as error:\n    (out", "        if message['type']=='voice.start' or str(message.get('id','')).startswith('speak1') or str(message.get('id','')).startswith('speak2') or str(message.get('id','')).startswith('speak3'):\n            time.sleep(10)\nexcept Exception as error:\n    (out")
driver=driver.replace("'stacks168.log','catalog.json'", "'stacks168.log','catalog.json','tts-state.jsonl'")
driver += "\n(out/'STOP_AUDIO').touch(exist_ok=False)\n"
(root/'scratchpad/c03-sidecar168.py').write_text(driver,encoding='utf-8')
entry=(root/'scratchpad/c03-sidecar165-entry.py').read_text(encoding='utf-8').replace('165','168')
entry=entry.replace('import runpy','import runpy\nimport json\nimport time\nfrom baxy_mind.voice_output import NeuralSpeechOutput')
entry=entry.replace("with (private/'stacks168.log')", "original_state = NeuralSpeechOutput._set_speaking\ndef observe_state(self, speaking):\n    original_state(self, speaking)\n    with (private/'tts-state.jsonl').open('a', encoding='utf-8') as state_log:\n        state_log.write(json.dumps({'time':time.monotonic(), 'speaking':speaking, 'error':self.last_error, 'voice':self.voice_name})+'\\n')\nNeuralSpeechOutput._set_speaking = observe_state\nwith (private/'stacks168.log')")
(root/'scratchpad/c03-sidecar168-entry.py').write_text(entry,encoding='utf-8')
note='''# C03 — UI166 vuelve a responder; salida física aún falla

Fuente164191pass/0skips19,14s. Fast49634exit0, Release3,56s0warnings/errors.
166 App36988, launcher7728, monitor30244; py main.py real. Captura7514 y launcher65506
exit0/propios cerrados. Sin nuevas ediciones de producto tras164.
Tres preguntas consumidas en UI: «Dime la hora.» -> «Son las10:55.»;
«What time is it?» -> «It is10:56.»; «Dime la hora, please.» -> «Son las10:56.».
Payloads Core verificados y composición first/stop en idioma es/en/mixed.
Latencias submit.received->visible.text:1325,475/1045,566/1043,858ms.
Un solo catalog.configure, voiceon durante toda la observación, sin reinicios.
Recursos246,77s:3499,50390625MiBVRAM, atribución disponible;5964,53125MiBRAM.
Audio263,89s,0overflows, threadsStopped y restauración exacta0/mutedtrue.

167 ASR local Parakeet CPU sobre mic/loopback crudo y normalizado, cuatroventanas
de voice.speak-0,5s a+15s. NO recupera las frases completas: mic vacío cuatro;
loop saludo/EN vacío, ES «Yeah.» sólo crudo, mixto «Gracias.»/«Thank you.».
Hay señal capturada, no es el silencio de158, pero no acreditar audio útil.
No afirmar aún que sean cortes por barge:166 no guardó ese evento interno.
Fuente164 corrige bloqueo161 y latencia158; NO cierra audio148 ni C03.

168 siguiente: fullsidecar/catálogo/modelo, mismos cuatrotextos publicados166,
captura física. Registra eventos JSONL y sólo añade observación de last_error
al cambiar speaking; no taps porframe ni modifica DSP. Distinguir cancelación
barge_in de error/deadline de reproducción antes de cualquier ajuste.
'''
(base/'ASTRA-TRAMO-166_168.md').write_text(note,encoding='utf-8')
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name
    intro='# Último: UI166 responde, audio167 falla;168 preparado\n\nASTRA-TRAMO-166_168.md manda. Fuente164191tests/Fast verdes. UI treshorasveraces ~1s, voiceon,3499,50MiBVRAM; grabación sin frases completas según ASR167. Sin procesos propios activos.168 registra eventos y errorTTS del fullsidecar con audio físico. No Full, wake no aprobado ni reserva aceptada.\n\n'
    p.write_text(intro+p.read_text(encoding='utf-8'),encoding='utf-8')
p=base/'RELEVO_ACTIVO.json'
d=json.loads(p.read_text(encoding='utf-8'))
d.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='Fuente164191tests/Fast verdes. UI1663 respuestas veraces ~1s y3499,50MiBVRAM; audio no acredita frases completas167.',continuation='Captura168 y fullsidecar168 preparados; distinguir barge_in de error TTS con mismos cuatrotextos166 y observaciónsóloenstate. Fuente164 intacta; no Full ni aceptación.')
p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('168 preregistered; no source changes.')
